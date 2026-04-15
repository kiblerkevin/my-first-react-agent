from collections import defaultdict, Counter
import yaml

from models.inputs.fetch_articles_input import FetchArticlesInput
from models.inputs.fetch_scores_input import FetchScoresInput
from models.inputs.summarize_article_input import SummarizeArticleInput
from models.inputs.create_blog_draft_input import CreateBlogDraftInput
from models.inputs.deduplicate_articles_input import DeduplicateArticlesInput
from models.inputs.evaluate_blog_post_input import EvaluateBlogPostInput
from models.inputs.create_blog_taxonomy_input import CreateBlogTaxonomyInput
from tools.fetch_articles_tool import FetchArticlesTool
from tools.fetch_scores_tool import FetchScoresTool
from tools.summarize_article_tool import SummarizeArticleTool
from tools.create_blog_draft_tool import CreateBlogDraftTool
from tools.deduplicate_articles_tool import DeduplicateArticlesTool
from tools.evaluate_blog_post_tool import EvaluateBlogPostTool
from tools.create_blog_taxonomy_tool import CreateBlogTaxonomyTool

ORCHESTRATION_CONFIG_PATH = 'config/orchestration.yaml'

MAX_ARTICLES_PER_TEAM = 2


def main():
    with open(ORCHESTRATION_CONFIG_PATH, 'r') as f:
        orchestration_config = yaml.safe_load(f)
    max_retries = orchestration_config['revision_loop']['max_retries']
    criterion_floors = orchestration_config['revision_loop']['criterion_floors']

    fetch_articles_tool = FetchArticlesTool()
    fetch_scores_tool = FetchScoresTool()
    summarize_tool = SummarizeArticleTool()
    draft_tool = CreateBlogDraftTool()
    deduplicate_tool = DeduplicateArticlesTool()
    evaluate_tool = EvaluateBlogPostTool()
    taxonomy_tool = CreateBlogTaxonomyTool()

    # Step 1: Fetch scores
    print("--- Step 1: Fetch Scores ---")
    scores_output = fetch_scores_tool.execute(FetchScoresInput())
    print(f"Scores fetched: {scores_output.score_count}")
    if scores_output.errors:
        print(f"Errors: {scores_output.errors}")

    # Step 2: Fetch articles
    print("\n--- Step 2: Fetch Articles ---")
    articles_output = fetch_articles_tool.execute(FetchArticlesInput())
    print(f"Articles fetched: {articles_output.article_count}")
    if articles_output.errors:
        print(f"Errors: {articles_output.errors}")

    # Step 3: Deduplicate articles within each team
    print("\n--- Step 3: Deduplicate Articles ---")
    dedup_output = deduplicate_tool.execute(DeduplicateArticlesInput(
        articles=articles_output.articles
    ))
    print(f"Duplicates removed: {dedup_output.duplicate_count}")
    if dedup_output.duplicate_groups:
        for group in dedup_output.duplicate_groups:
            print(f"  Collapsed: {group[0][:60]}... ({len(group) - 1} duplicate(s))")

    # Step 4: Summarize top 2 articles per team
    print(f"\n--- Step 4: Summarize Articles (top {MAX_ARTICLES_PER_TEAM} per team) ---")
    articles_by_team = defaultdict(list)
    for article in dedup_output.unique_articles:
        articles_by_team[article.get('team', 'Unknown')].append(article)

    summaries = []
    for team, articles in articles_by_team.items():
        top_articles = sorted(
            articles, key=lambda a: a.get('relevance_score', 0), reverse=True
        )[:MAX_ARTICLES_PER_TEAM]

        for article in top_articles:
            print(f"  Summarizing [{team}]: {article.get('title', '')[:70]}")
            summary = summarize_tool.execute(SummarizeArticleInput(
                url=article['url'],
                title=article['title'],
                team=team,
                published_at=article.get('publishedAt', '')
            ))
            summaries.append(summary.model_dump())

    relevant = [s for s in summaries if s.get('is_relevant')]
    print(f"Summaries collected: {len(summaries)} total, {len(relevant)} relevant")

    # Steps 5-6: Draft + evaluate with revision loop
    print("\n--- Steps 5-6: Draft, Evaluate, and Revise ---")
    best_draft = None
    best_evaluation = None
    revision_notes = None
    current_draft = None

    for attempt in range(max_retries):
        print(f"\n  Attempt {attempt + 1}/{max_retries}")

        draft = draft_tool.execute(CreateBlogDraftInput(
            summaries=summaries,
            scores=scores_output.scores,
            current_draft=current_draft,
            revision_notes=revision_notes
        ))

        evaluation = evaluate_tool.execute(EvaluateBlogPostInput(
            title=draft.title,
            content=draft.content,
            excerpt=draft.excerpt,
            summaries=summaries,
            scores=scores_output.scores
        ))

        print(f"  Overall score: {evaluation.overall_score}/10")
        for criterion, score in evaluation.criteria_scores.items():
            floor = criterion_floors.get(criterion, 0)
            status = '✓' if score >= floor else '✗'
            print(f"    {status} {criterion:<14} {score}/10 (floor: {floor})")

        if best_evaluation is None or evaluation.overall_score > best_evaluation.overall_score:
            best_draft = draft
            best_evaluation = evaluation

        failing = {
            criterion: suggestions
            for criterion, suggestions in evaluation.improvement_suggestions.items()
            if evaluation.criteria_scores.get(criterion, 0) < criterion_floors.get(criterion, 0)
        }

        if not failing:
            print(f"  All criterion floors met on attempt {attempt + 1}.")
            break

        revision_notes = failing
        current_draft = draft.content
        print(f"  Failing criteria: {list(failing.keys())} — revising...")
    else:
        print(f"  Max retries reached. Using best draft (score: {best_evaluation.overall_score}/10).")

    print(f"\nFinal Title:         {best_draft.title}")
    print(f"Final Teams covered: {best_draft.teams_covered}")
    print(f"Final Articles used: {best_draft.article_count}")
    print(f"Final Excerpt:       {best_draft.excerpt}")
    print(f"Final Overall score: {best_evaluation.overall_score}/10")
    print(f"\nContent preview (first 1000 chars):\n{best_draft.content[:1000]}")

    # Step 7: Create blog taxonomy
    print("\n--- Step 7: Create Blog Taxonomy ---")
    all_players = []
    for s in relevant:
        all_players.extend(s.get('players_mentioned', []))

    taxonomy = taxonomy_tool.execute(CreateBlogTaxonomyInput(
        teams_covered=best_draft.teams_covered,
        players_mentioned=all_players
    ))

    print("Categories:")
    for cat in taxonomy.categories:
        wp_id = cat.get('wordpress_id') or 'unresolved'
        print(f"  {cat['name']} (local_id={cat['id']}, wp_id={wp_id})")
    print("Tags:")
    for tag in taxonomy.tags:
        wp_id = tag.get('wordpress_id') or 'unresolved'
        print(f"  {tag['name']} (local_id={tag['id']}, wp_id={wp_id})")
    if taxonomy.new_categories:
        print(f"New categories created: {taxonomy.new_categories}")
    if taxonomy.new_tags:
        print(f"New tags created: {taxonomy.new_tags}")


if __name__ == "__main__":
    main()
