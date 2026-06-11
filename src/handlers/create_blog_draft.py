"""Lambda handler: Draft and evaluate blog post via revision agent.

This is the longest-running Lambda (900s timeout). It runs the full
revision loop: draft → evaluate → revise until criterion floors are met.
"""

from agent.revision_agent import RevisionAgent
from src.shared.dynamo_memory import DynamoMemory

memory = DynamoMemory()


def handler(event, context):
    """Run revision agent to produce and evaluate a blog draft."""
    run_id = event.get('run_id')

    checkpoint = memory.get_checkpoint(run_id)
    scores_data = checkpoint['data']['fetch_scores']
    summaries_data = checkpoint['data']['summarize_articles']

    relevant = summaries_data['relevant']
    scores = scores_data['scores']

    # Load most recent rejection feedback
    rejection_feedback = None
    recent_rejection = memory.get_most_recent_rejection()
    if recent_rejection:
        rejection_feedback = recent_rejection['feedback']

    # Run revision agent
    agent = RevisionAgent()
    result = agent.run(
        summaries=relevant,
        scores=scores,
        rejection_feedback=rejection_feedback,
    )

    best_draft = result['best_draft']
    best_evaluation = result['best_evaluation']

    # Persist draft + evaluations
    summary_id = memory.save_blog_draft(
        {
            'title': best_draft['title'],
            'content': best_draft['content'],
            'excerpt': best_draft.get('excerpt', ''),
            'teams_covered': best_draft.get('teams_covered', []),
            'article_count': best_draft.get('article_count', 0),
            'overall_score': best_evaluation.get('overall_score', 0),
        }
    )
    for eval_data in result['all_evaluations']:
        memory.save_evaluation(summary_id, eval_data)

    # Update revision metrics
    all_drafts = result.get('all_drafts', [])
    all_evaluations = result['all_evaluations']
    score_progression = [e.get('overall_score', 0) for e in all_evaluations]
    draft_iterations = [
        {
            'title': d.get('title', ''),
            'excerpt': d.get('excerpt', ''),
            'teams_covered': d.get('teams_covered', []),
        }
        for d in all_drafts
    ]
    memory.update_workflow_revision_metrics(
        run_id=run_id,
        tool_calls=getattr(agent, '_last_tool_calls', 0),
        draft_attempts=len(all_drafts),
        score_progression=score_progression,
        draft_iterations=draft_iterations,
    )

    # Save to checkpoint for downstream steps
    memory.save_checkpoint(
        run_id,
        'draft_and_evaluate',
        {
            'best_draft': best_draft,
            'best_evaluation': best_evaluation,
            'summary_id': summary_id,
        },
    )

    return {
        'title': best_draft.get('title', ''),
        'overall_score': best_evaluation.get('overall_score', 0),
        'summary_id': summary_id,
    }
