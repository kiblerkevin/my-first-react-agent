"""Lambda handler: Housekeeping — update workflow status, run drift detection."""

import boto3

from src.shared.dynamo_memory import DynamoMemory
from src.shared.secrets import get_secret
from utils.drift_detector import DriftDetector

memory = DynamoMemory()
ses = boto3.client('ses')


def handler(event, context):
    """Mark workflow success and run drift detection."""
    run_id = event.get('run_id')

    # Get final counts from checkpoint
    checkpoint = memory.get_checkpoint(run_id)
    scores_data = checkpoint['data'].get('fetch_scores', {})
    articles_data = checkpoint['data'].get('fetch_articles', {})
    summaries_data = checkpoint['data'].get('summarize_articles', {})
    approval_data = checkpoint['data'].get('send_approval_email', {})
    draft_data = checkpoint['data'].get('draft_and_evaluate', {})

    # Mark workflow as success
    memory.update_workflow_run(
        run_id,
        {
            'status': 'success',
            'steps_completed': [
                'fetch_scores',
                'fetch_articles',
                'deduplicate_articles',
                'summarize_articles',
                'draft_and_evaluate',
                'create_taxonomy',
                'send_approval_email',
                'housekeeping',
            ],
            'scores_fetched': scores_data.get('score_count'),
            'articles_fetched': articles_data.get('article_count'),
            'articles_new': articles_data.get('new_article_count'),
            'summaries_count': len(summaries_data.get('relevant', [])),
            'overall_score': draft_data.get('best_evaluation', {}).get('overall_score'),
            'email_sent': approval_data.get('email_sent'),
        },
    )

    # Drift detection
    _run_drift_check(run_id)

    return {'status': 'success'}


def _run_drift_check(run_id: str) -> None:
    try:
        detector = DriftDetector(memory=memory)
        results = detector.check(run_id=run_id)

        email_from = get_secret('EMAIL_FROM')
        error_email_to = get_secret('ERROR_EMAIL_TO') or get_secret('EMAIL_TO')

        if results.get('new_alerts'):
            _send_drift_alert(results['new_alerts'], email_from, error_email_to)

        if results.get('recoveries'):
            _send_drift_recovery(results['recoveries'], email_from, error_email_to)
    except Exception:
        pass  # Drift check failure should not fail the workflow


def _send_drift_alert(alerts: list, email_from: str, email_to: str) -> None:
    metric_names = ', '.join(a['metric_name'] for a in alerts)
    rows = ''.join(
        f'<tr><td>{a["metric_name"]}</td><td>{a.get("value")}</td><td>{a.get("threshold")}</td></tr>'
        for a in alerts
    )
    html = f"""<html><body>
        <h1 style="color: #ff9800;">⚠️ Drift Alert</h1>
        <table border='1' cellpadding='8'><tr><th>Metric</th><th>Value</th><th>Threshold</th></tr>{rows}</table>
    </body></html>"""
    ses.send_email(
        Source=email_from,
        Destination={'ToAddresses': [email_to]},
        Message={
            'Subject': {'Data': f'[Drift Alert] {metric_names}'},
            'Body': {'Html': {'Data': html}},
        },
    )


def _send_drift_recovery(recoveries: list, email_from: str, email_to: str) -> None:
    metric_names = ', '.join(r['metric_name'] for r in recoveries)
    rows = ''.join(
        f'<tr><td>{r["metric_name"]}</td><td>{r.get("value")}</td></tr>'
        for r in recoveries
    )
    html = f"""<html><body>
        <h1 style="color: #28a745;">✅ Drift Recovered</h1>
        <table border='1' cellpadding='8'><tr><th>Metric</th><th>Value</th></tr>{rows}</table>
    </body></html>"""
    ses.send_email(
        Source=email_from,
        Destination={'ToAddresses': [email_to]},
        Message={
            'Subject': {'Data': f'[Drift Recovered] {metric_names}'},
            'Body': {'Html': {'Data': html}},
        },
    )
