from collections import defaultdict
from datetime import datetime, timezone

import yaml
from langfuse import observe

from models.inputs.fetch_articles_input import FetchArticlesInput
from models.inputs.fetch_scores_input import FetchScoresInput
from models.inputs.summarize_article_input import SummarizeArticleInput
from models.inputs.deduplicate_articles_input import DeduplicateArticlesInput
from models.inputs.create_blog_taxonomy_input import CreateBlogTaxonomyInput
from models.inputs.send_approval_email_input import SendApprovalEmailInput
from tools.fetch_articles_tool import FetchArticlesTool
from tools.fetch_scores_tool import FetchScoresTool
from tools.summarize_article_tool import SummarizeArticleTool
from tools.deduplicate_articles_tool import DeduplicateArticlesTool
from tools.create_blog_taxonomy_tool import CreateBlogTaxonomyTool
from tools.send_approval_email_tool import SendApprovalEmailTool, send_failure_email
from agent.revision_agent import RevisionAgent
from memory.memory import Memory
from utils.logger.logger import setup_logger


logger = setup_logger(__name__)

ORCHESTRATION_CONFIG_PATH = 'config/orchestration.yaml'


@observe()
def run_daily_workflow(max_articles_per_team: int = 2, resume_run_id: str = None) -> dict:
    """
    Runs the full daily workflow (steps 1-8).
    If resume_run_id is provided, resumes from the last completed step of that run.
    """
    memory = Memory()

    if resume_run_id:
        run_id = resume_run_id
        checkpoint = memory.get_checkpoint(run_id)
        if not checkpoint:
            logger.warning(f"No checkpoint found for {run_id} — starting fresh.")
            checkpoint = None
        else:
            logger.info(f"Resuming run {run_id} from checkpoint. Steps completed: {checkpoint['steps_completed']}")
    else:
        run_id = datetime.now(timezone.utc).isoformat()
        memory.create_workflow_run(run_id)
        checkpoint = None

    completed = checkpoint['steps_completed'] if checkpoint else []
    cp_data = checkpoint['data'] if checkpoint else {}
    steps_completed = list(completed)

    try:
        return _execute_workflow(run_id, memory, steps_completed, cp_data, max_articles_per_team)
    except Exception as e:
        logger.error(f"Workflow {run_id} failed: {e}")
        memory.update_workflow_run(run_id, {
            'status': 'failed',
            'error': str(e),
            'steps_completed': steps_completed
        })
        send_failure_email(
            run_id=run_id,
            error=str(e),
            steps_completed=steps_completed
        )
        raise


def _step_done(step_name: str, steps_completed: list) -> bool:
    return step_name in steps_completed


@observe()
def _execute_workflow(run_id: str, memory: Memory, steps_completed: list, cp_data: dict, max_articles_per_team: int) -> dict:
    with open(ORCHESTRATION_CONFIG_PATH, 'r') as f:
        orchestration_config = yaml.safe_load(f)

    fetch_articles_tool = FetchArticlesTool()
    fetch_scores_tool = FetchScoresTool()
    summarize_tool = SummarizeArticleTool()
    deduplicate_tool = DeduplicateArticlesTool()
    taxonomy_tool = CreateBlogTaxonomyTool()
    approval_tool = SendApprovalEmailTool()

    # Load most recent rejection feedback
    rejection_feedback = None
    recent_rejection = memory.get_most_recent_rejection()
    if recent_rejection:
        rejection_feedback = recent_rejection['feedback']
        logger.info(f"Loaded rejection feedback from '{recent_rejection['blog_title']}': {rejection_feedback[:80]}...")
    else:
        logger.info("No previous rejection feedback found.")

    # Step 1: Fetch scores
    if _step_done('fetch_scores', steps_completed):
        logger.info("Step 1: Restoring scores from checkpoint...")
        scores_data = cp_data['fetch_scores']
    else:
        logger.info("Step 1: Fetching scores...")
        scores_output = fetch_scores_tool.execute(FetchScoresInput(run_id=run_id))
        scores_data = {'scores': scores_output.scores, 'score_count': scores_output.score_count}
        logger.info(f"Scores fetched: {scores_data['score_count']}")
        steps_completed.append('fetch_scores')
        memory.save_checkpoint(run_id, 'fetch_scores', scores_data)

    # Step 2: Fetch articles
    if _step_done('fetch_articles', steps_completed):
        logger.info("Step 2: Restoring articles from checkpoint...")
        articles_data = cp_data['fetch_articles']
    else:
        logger.info("Step 2: Fetching articles...")
        articles_output = fetch_articles_tool.execute(FetchArticlesInput(run_id=run_id))
        articles_data = {
            'articles': articles_output.articles,
            'new_articles': articles_output.new_articles,
            'article_count': articles_output.article_count,
            'new_article_count': articles_output.new_article_count,
            'filtered_article_count': articles_output.filtered_article_count
        }
        logger.info(
            f"Articles fetched: {articles_data['article_count']} total, "
            f"{articles_data['new_article_count']} new, "
            f"{articles_data['filtered_article_count']} previously seen"
        )
        steps_completed.append('fetch_articles')
        memory.save_checkpoint(run_id, 'fetch_articles', articles_data)

    if articles_data['new_article_count'] == 0:
        logger.info("No new articles found — skipping today's workflow.")
        result = {
            'skipped': True,
            'skip_reason': 'No new articles found.',
            'run_id': run_id,
            'scores_fetched': scores_data['score_count']
        }
        memory.update_workflow_run(run_id, {
            'status': 'skipped',
            'skip_reason': result['skip_reason'],
            'steps_completed': steps_completed,
            'scores_fetched': scores_data['score_count'],
            'articles_fetched': articles_data['article_count'],
            'articles_new': 0
        })
        return result

    # Step 3: Deduplicate articles
    if _step_done('deduplicate_articles', steps_completed):
        logger.info("Step 3: Restoring deduplicated articles from checkpoint...")
        dedup_data = cp_data['deduplicate_articles']
    else:
        logger.info("Step 3: Deduplicating articles...")
        dedup_output = deduplicate_tool.execute(DeduplicateArticlesInput(
            articles=articles_data['new_articles']
        ))
        dedup_data = {
            'unique_articles': dedup_output.unique_articles,
            'duplicate_count': dedup_output.duplicate_count
        }
        logger.info(f"Duplicates removed: {dedup_data['duplicate_count']}")
        steps_completed.append('deduplicate_articles')
        memory.save_checkpoint(run_id, 'deduplicate_articles', dedup_data)

    # Step 4: Summarize top articles per team
    if _step_done('summarize_articles', steps_completed):
        logger.info("Step 4: Restoring summaries from checkpoint...")
        summaries = cp_data['summarize_articles']['summaries']
        relevant = cp_data['summarize_articles']['relevant']
    else:
        logger.info(f"Step 4: Summarizing articles (top {max_articles_per_team} per team)...")
        articles_by_team = defaultdict(list)
        for article in dedup_data['unique_articles']:
            articles_by_team[article.get('team', 'Unknown')].append(article)

        summaries = []
        team_stats = {}  # track per-team cache hits/misses
        for team, articles in articles_by_team.items():
            top_articles = sorted(
                articles, key=lambda a: a.get('relevance_score', 0), reverse=True
            )[:max_articles_per_team]

            stats = {'team': team, 'articles_fetched': len(articles), 'articles_summarized': 0, 'cache_hits': 0, 'cache_misses': 0}
            for article in top_articles:
                logger.info(f"  Summarizing [{team}]: {article.get('title', '')[:70]}")
                summary = summarize_tool.execute(SummarizeArticleInput(
                    url=article['url'],
                    title=article['title'],
                    team=team,
                    published_at=article.get('publishedAt', '')
                ))
                summaries.append(summary.model_dump())
                stats['articles_summarized'] += 1
                if summarize_tool.last_cache_hit:
                    stats['cache_hits'] += 1
                else:
                    stats['cache_misses'] += 1
            team_stats[team] = stats

        relevant = [s for s in summaries if s.get('is_relevant')]
        logger.info(f"Summaries: {len(summaries)} total, {len(relevant)} relevant")
        steps_completed.append('summarize_articles')
        memory.save_checkpoint(run_id, 'summarize_articles', {
            'summaries': summaries,
            'relevant': relevant
        })

        # Persist summary stats
        db_id = memory.get_workflow_run_db_id(run_id)
        if db_id:
            memory.save_summary_stats(db_id, list(team_stats.values()))

    if len(relevant) == 0:
        logger.info("No relevant summaries — skipping draft.")
        result = {
            'skipped': True,
            'skip_reason': 'No relevant article summaries after summarization.',
            'run_id': run_id,
            'scores_fetched': scores_data['score_count'],
            'articles_fetched': articles_data['new_article_count']
        }
        memory.update_workflow_run(run_id, {
            'status': 'skipped',
            'skip_reason': result['skip_reason'],
            'steps_completed': steps_completed,
            'scores_fetched': scores_data['score_count'],
            'articles_fetched': articles_data['article_count'],
            'articles_new': articles_data['new_article_count'],
            'summaries_count': len(summaries)
        })
        return result

    # Steps 5-6: Draft + evaluate via revision agent
    if _step_done('draft_and_evaluate', steps_completed):
        logger.info("Steps 5-6: Restoring draft and evaluation from checkpoint...")
        draft_eval_data = cp_data['draft_and_evaluate']
        best_draft_data = draft_eval_data['best_draft']
        best_eval_data = draft_eval_data['best_evaluation']

        from models.outputs.create_blog_draft_output import CreateBlogDraftOutput
        from models.outputs.evaluate_blog_post_output import EvaluateBlogPostOutput
        best_draft = CreateBlogDraftOutput(**best_draft_data)
        best_evaluation = EvaluateBlogPostOutput(**best_eval_data)
        all_evaluations = draft_eval_data['all_evaluations']
    else:
        logger.info("Steps 5-6: Starting revision agent...")
        revision_agent = RevisionAgent()
        agent_result = revision_agent.run(
            summaries=summaries,
            scores=scores_data['scores'],
            rejection_feedback=rejection_feedback
        )

        from models.outputs.create_blog_draft_output import CreateBlogDraftOutput
        from models.outputs.evaluate_blog_post_output import EvaluateBlogPostOutput
        best_draft = CreateBlogDraftOutput(**agent_result['best_draft'])
        best_evaluation = EvaluateBlogPostOutput(**agent_result['best_evaluation'])
        all_evaluations = agent_result['all_evaluations']
        all_drafts = agent_result.get('all_drafts', [])

        logger.info(f"Final draft: '{best_draft.title}' | score: {best_evaluation.overall_score}/10")
        steps_completed.append('draft_and_evaluate')
        memory.save_checkpoint(run_id, 'draft_and_evaluate', {
            'best_draft': best_draft.model_dump(),
            'best_evaluation': best_evaluation.model_dump(),
            'all_evaluations': all_evaluations
        })

        # Persist revision metrics and draft iterations
        score_progression = [e.get('overall_score', 0) for e in all_evaluations]
        draft_iterations = [{
            'title': d.get('title', ''),
            'content': d.get('content', ''),
            'excerpt': d.get('excerpt', ''),
            'teams_covered': d.get('teams_covered', [])
        } for d in all_drafts]
        memory.update_workflow_revision_metrics(
            run_id=run_id,
            tool_calls=getattr(revision_agent, '_last_tool_calls', 0),
            draft_attempts=len(all_drafts),
            score_progression=score_progression,
            draft_iterations=draft_iterations
        )

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
    if _step_done('create_taxonomy', steps_completed):
        logger.info("Step 7: Restoring taxonomy from checkpoint...")
        taxonomy_data = cp_data['create_taxonomy']
    else:
        logger.info("Step 7: Creating taxonomy...")
        all_players = []
        for s in relevant:
            all_players.extend(s.get('players_mentioned', []))

        taxonomy = taxonomy_tool.execute(CreateBlogTaxonomyInput(
            teams_covered=best_draft.teams_covered,
            players_mentioned=all_players
        ))
        taxonomy_data = {
            'categories': taxonomy.categories,
            'tags': taxonomy.tags
        }
        logger.info(f"Taxonomy: {len(taxonomy.categories)} categories, {len(taxonomy.tags)} tags")
        steps_completed.append('create_taxonomy')
        memory.save_checkpoint(run_id, 'create_taxonomy', taxonomy_data)

    # Step 8: Send approval email
    if _step_done('send_approval_email', steps_completed):
        logger.info("Step 8: Approval email already sent — skipping.")
        approval_data = cp_data['send_approval_email']
    else:
        logger.info("Step 8: Sending approval email...")
        approval_result = approval_tool.execute(SendApprovalEmailInput(
            title=best_draft.title,
            content=best_draft.content,
            excerpt=best_draft.excerpt,
            categories=taxonomy_data['categories'],
            tags=taxonomy_data['tags'],
            evaluation_scores=best_evaluation.criteria_scores,
            summaries=summaries,
            scores=scores_data['scores']
        ))
        approval_data = {
            'email_sent': approval_result.email_sent,
            'token': approval_result.token,
            'error': approval_result.error
        }
        logger.info(f"Approval email sent: {approval_data['email_sent']} | token: {approval_data['token'][:20]}...")
        steps_completed.append('send_approval_email')
        memory.save_checkpoint(run_id, 'send_approval_email', approval_data)

    result = {
        'skipped': False,
        'skip_reason': None,
        'run_id': run_id,
        'title': best_draft.title,
        'teams_covered': best_draft.teams_covered,
        'article_count': best_draft.article_count,
        'overall_score': best_evaluation.overall_score,
        'email_sent': approval_data['email_sent'],
        'token': approval_data['token'],
        'error': approval_data.get('error')
    }

    memory.update_workflow_run(run_id, {
        'status': 'success',
        'steps_completed': steps_completed,
        'scores_fetched': scores_data['score_count'],
        'articles_fetched': articles_data['article_count'],
        'articles_new': articles_data['new_article_count'],
        'summaries_count': len(relevant),
        'overall_score': best_evaluation.overall_score,
        'email_sent': approval_data['email_sent']
    })

    # Housekeeping
    memory.purge_old_logs()

    return result
