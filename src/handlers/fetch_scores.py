"""Lambda handler: Fetch scores from ESPN API."""

from src.shared.dynamo_memory import DynamoMemory
from utils.article_collectors.api_collectors.espn_collector import ESPNCollector

memory = DynamoMemory()
collector = ESPNCollector()


def handler(event, context):
    """Fetch scores from ESPN and save to checkpoint."""
    run_id = event.get('run_id')
    memory.create_workflow_run(run_id)

    try:
        scores = collector.collect_articles()
        memory.save_api_call_result(run_id, 'espn', 'success', len(scores))
        memory.save_checkpoint(
            run_id, 'fetch_scores', {'scores': scores, 'score_count': len(scores)}
        )
        return {'score_count': len(scores)}
    except Exception as e:
        memory.save_api_call_result(run_id, 'espn', 'error', error=str(e))
        raise
