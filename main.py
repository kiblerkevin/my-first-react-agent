from collections import defaultdict

from models.inputs.fetch_articles_input import FetchArticlesInput
from models.inputs.fetch_scores_input import FetchScoresInput
from models.inputs.summarize_article_input import SummarizeArticleInput
from models.inputs.create_blog_draft_input import CreateBlogDraftInput
from tools.fetch_articles_tool import FetchArticlesTool
from tools.fetch_scores_tool import FetchScoresTool
from tools.summarize_article_tool import SummarizeArticleTool
from tools.create_blog_draft_tool import CreateBlogDraftTool

MAX_ARTICLES_PER_TEAM = 2


def main():
    fetch_articles_tool = FetchArticlesTool()
    fetch_scores_tool = FetchScoresTool()
    summarize_tool = SummarizeArticleTool()
    draft_tool = CreateBlogDraftTool()

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

    # Step 3: Summarize top 2 articles per team
    print(f"\n--- Step 3: Summarize Articles (top {MAX_ARTICLES_PER_TEAM} per team) ---")
    articles_by_team = defaultdict(list)
    for article in articles_output.articles:
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

    # Step 4: Create blog draft
    print("\n--- Step 4: Create Blog Draft ---")
    draft = draft_tool.execute(CreateBlogDraftInput(
        summaries=summaries,
        scores=scores_output.scores
    ))

    print(f"\nTitle:         {draft.title}")
    print(f"Teams covered: {draft.teams_covered}")
    print(f"Articles used: {draft.article_count}")
    print(f"Excerpt:       {draft.excerpt}")
    print(f"\nContent preview (first 1000 chars):\n{draft.content[:1000]}")


if __name__ == "__main__":
    main()
