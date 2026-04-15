from collections import defaultdict

import yaml

from models.inputs.fetch_articles_input import FetchArticlesInput
from models.inputs.fetch_scores_input import FetchScoresInput
from models.inputs.summarize_article_input import SummarizeArticleInput
from models.inputs.create_blog_draft_input import CreateBlogDraftInput
from models.inputs.deduplicate_articles_input import DeduplicateArticlesInput
from models.inputs.evaluate_blog_post_input import EvaluateBlogPostInput
from models.inputs.create_blog_taxonomy_input import CreateBlogTaxonomyInput
from models.inputs.send_approval_email_input import SendApprovalEmailInput
from tools.fetch_articles_tool import FetchArticlesTool
from tools.fetch_scores_tool import FetchScoresTool
from tools.summarize_article_tool import SummarizeArticleTool
from tools.create_blog_draft_tool import CreateBlogDraftTool
from tools.deduplicate_articles_tool import DeduplicateArticlesTool
from tools.evaluate_blog_post_tool import EvaluateBlogPostTool
from tools.create_blog_taxonomy_tool import CreateBlogTaxonomyTool
from tools.send_approval_email_tool import SendApprovalEmailTool
from memory.memory import Memory
from utils.logger.logger import setup_logger


logger = setup_logger(__name__)

ORCHESTRATION_CONFIG_PATH = 'config/orchestration.yaml'


def run_daily_workflow(max_articles_per_team: int = 2) -> dict:
    """
    Runs the full daily workflow (steps 1-8):
    fetch scores → fetch articles → deduplicate → summarize → draft → evaluate/revise → taxonomy → send approval email

    Returns a dict with workflow results for logging/debugging.
    """
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
    approval_tool = SendApprovalEmailTool()
    memory = Memory()

    # Step 1: Fetch scores
    logger.info("Step 1: Fetching scores...")
    scores_output = fetch_scores_tool.execute(FetchScoresInput())
    logger.info(f"Scores fetched: {scores_output.score_count}")

    # Step 2: Fetch articles
    logger.info("Step 2: Fetching articles...")
    articles_output = fetch_articles_tool.execute(FetchArticlesInput())
    logger.info(
        f"Articles fetched: {articles_output.article_count} total, "
        f"{articles_output.new_article_count} new, "
        f"{articles_output.filtered_article_count} previously seen"
    )

    # Step 3: Deduplicate articles
    logger.info("Step 3: Deduplicating articles...")
    dedup_output = deduplicate_tool.execute(DeduplicateArticlesInput(
        articles=articles_output.new_articles
    ))
    logger.info(f"Duplicates removed: {dedup_output.duplicate_count}")

    # Step 4: Summarize top articles per team
    logger.info(f"Step 4: Summarizing articles (top {max_articles_per_team} per team)...")
    articles_by_team = defaultdict(list)
    for article in dedup_output.unique_articles:
        articles_by_team[article.get('team', 'Unknown')].append(article)

    summaries = []
    for team, articles in articles_by_team.items():
        top_articles = sorted(
            articles, key=lambda a: a.get('relevance_score', 0), reverse=True
        )[:max_articles_per_team]

        for article in top_articles:
            logger.info(f"  Summarizing [{team}]: {article.get('title', '')[:70]}")
            summary = summarize_tool.execute(SummarizeArticleInput(
                url=article['url'],
                title=article['title'],
                team=team,
                published_at=article.get('publishedAt', '')
            ))
            summaries.append(summary.model_dump())

    relevant = [s for s in summaries if s.get('is_relevant')]
    logger.info(f"Summaries: {len(summaries)} total, {len(relevant)} relevant")

    # Steps 5-6: Draft + evaluate with revision loop
    logger.info("Steps 5-6: Drafting and evaluating...")
    best_draft = None
    best_evaluation = None
    revision_notes = None
    current_draft = None
    all_evaluations = []

    for attempt in range(max_retries):
        logger.info(f"  Draft attempt {attempt + 1}/{max_retries}")

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

        all_evaluations.append(evaluation.model_dump())
        logger.info(f"  Overall score: {evaluation.overall_score}/10")

        if best_evaluation is None or evaluation.overall_score > best_evaluation.overall_score:
            best_draft = draft
            best_evaluation = evaluation

        failing = {
            criterion: suggestions
            for criterion, suggestions in evaluation.improvement_suggestions.items()
            if evaluation.criteria_scores.get(criterion, 0) < criterion_floors.get(criterion, 0)
        }

        if not failing:
            logger.info(f"  All criterion floors met on attempt {attempt + 1}.")
            break

        revision_notes = failing
        current_draft = draft.content
        logger.info(f"  Failing criteria: {list(failing.keys())} — revising...")
    else:
        logger.info(f"  Max retries reached. Using best draft (score: {best_evaluation.overall_score}/10).")

    logger.info(f"Final draft: '{best_draft.title}' | score: {best_evaluation.overall_score}/10")

    # Persist blog draft and all evaluations
    summary_id = memory.save_blog_draft({
        'title': best_draft.title,
        'content': best_draft.content,
        'excerpt': best_draft.excerpt,
        'teams_covered': best_draft.teams_covered,
        'article_count': best_draft.article_count,
        'overall_score': best_evaluation.overall_score
    })
    for eval_data in all_evaluations:
        memory.save_evaluation(summary_id, eval_data)

    # Step 7: Create blog taxonomy
    logger.info("Step 7: Creating taxonomy...")
    all_players = []
    for s in relevant:
        all_players.extend(s.get('players_mentioned', []))

    taxonomy = taxonomy_tool.execute(CreateBlogTaxonomyInput(
        teams_covered=best_draft.teams_covered,
        players_mentioned=all_players
    ))
    logger.info(f"Taxonomy: {len(taxonomy.categories)} categories, {len(taxonomy.tags)} tags")

    # Step 8: Send approval email
    logger.info("Step 8: Sending approval email...")
    approval_result = approval_tool.execute(SendApprovalEmailInput(
        title=best_draft.title,
        content=best_draft.content,
        excerpt=best_draft.excerpt,
        categories=taxonomy.categories,
        tags=taxonomy.tags,
        evaluation_scores=best_evaluation.criteria_scores,
        summaries=summaries,
        scores=scores_output.scores
    ))

    logger.info(f"Approval email sent: {approval_result.email_sent} | token: {approval_result.token[:20]}...")

    return {
        'title': best_draft.title,
        'teams_covered': best_draft.teams_covered,
        'article_count': best_draft.article_count,
        'overall_score': best_evaluation.overall_score,
        'email_sent': approval_result.email_sent,
        'token': approval_result.token,
        'error': approval_result.error
    }
