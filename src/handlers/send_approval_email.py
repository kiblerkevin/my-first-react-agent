"""Lambda handler: Send approval email via SES."""

import json
from datetime import datetime, timedelta, timezone

import boto3
from itsdangerous import URLSafeTimedSerializer

from src.shared.config import APPROVAL_EXPIRY_HOURS
from src.shared.dynamo_memory import DynamoMemory
from src.shared.secrets import get_secret

memory = DynamoMemory()
ses = boto3.client('ses')


def handler(event, context):
    """Send approval email via SES with signed token."""
    run_id = event.get('run_id')

    checkpoint = memory.get_checkpoint(run_id)
    draft_data = checkpoint['data']['draft_and_evaluate']
    taxonomy_data = checkpoint['data']['create_taxonomy']
    scores_data = checkpoint['data']['fetch_scores']
    summaries_data = checkpoint['data']['summarize_articles']

    best_draft = draft_data['best_draft']
    best_evaluation = draft_data['best_evaluation']
    categories = taxonomy_data['categories']
    tags = taxonomy_data['tags']
    relevant = summaries_data['relevant']
    scores = scores_data['scores']

    secret_key = get_secret('APPROVAL_SECRET_KEY')
    base_url = get_secret('APPROVAL_BASE_URL')
    email_from = get_secret('EMAIL_FROM')
    email_to = get_secret('EMAIL_TO')

    serializer = URLSafeTimedSerializer(secret_key)
    token = serializer.dumps(best_draft['title'], salt='approval')
    expires_at = datetime.now(timezone.utc) + timedelta(hours=APPROVAL_EXPIRY_HOURS)

    # Persist approval record
    memory.create_pending_approval(
        {
            'token': token,
            'status': 'pending',
            'expires_at': expires_at,
            'blog_title': best_draft['title'],
            'blog_content': best_draft['content'],
            'blog_excerpt': best_draft.get('excerpt', ''),
            'taxonomy_data': json.dumps({'categories': categories, 'tags': tags}),
            'evaluation_data': json.dumps(best_evaluation.get('criteria_scores', {})),
            'summaries_data': json.dumps(relevant, default=str),
            'scores_data': json.dumps(scores, default=str),
        }
    )

    # Build and send email
    approve_url = f'{base_url}/#/approve/{token}'
    reject_url = f'{base_url}/#/reject/{token}'

    scores_html = ''
    criteria_scores = best_evaluation.get('criteria_scores', {})
    if criteria_scores:
        scores_html = "<h2>Evaluation Scores</h2><table border='1' cellpadding='8' cellspacing='0'>"
        for criterion, score in criteria_scores.items():
            scores_html += (
                f'<tr><td><strong>{criterion}</strong></td><td>{score}/10</td></tr>'
            )
        scores_html += '</table>'

    html_body = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto;">
        <h1>Blog Post Approval Request</h1>
        <p><strong>Title:</strong> {best_draft['title']}</p>
        <p><strong>Overall Score:</strong> {best_evaluation.get('overall_score', 0)}/10</p>
        <p><strong>Expires:</strong> {expires_at.strftime('%B %d, %Y at %I:%M %p UTC')}</p>
        {scores_html}
        <h2>Preview</h2>
        <div style="border: 1px solid #ccc; padding: 20px; background: #fafafa;">
            {best_draft['content'][:2000]}{'...' if len(best_draft.get('content', '')) > 2000 else ''}
        </div>
        <div style="margin: 30px 0; text-align: center;">
            <a href="{approve_url}" style="background-color: #28a745; color: white; padding: 15px 40px; text-decoration: none; border-radius: 5px; font-size: 18px; margin-right: 20px;">✅ Approve</a>
            <a href="{reject_url}" style="background-color: #dc3545; color: white; padding: 15px 40px; text-decoration: none; border-radius: 5px; font-size: 18px;">❌ Reject</a>
        </div>
        <p style="color: #666; font-size: 12px;">Expires in {APPROVAL_EXPIRY_HOURS} hours.</p>
    </body></html>
    """

    try:
        ses.send_email(
            Source=email_from,
            Destination={'ToAddresses': [email_to]},
            Message={
                'Subject': {'Data': f'[Approval Required] {best_draft["title"]}'},
                'Body': {'Html': {'Data': html_body}},
            },
        )
        email_sent = True
    except Exception:
        email_sent = False

    memory.save_checkpoint(
        run_id,
        'send_approval_email',
        {
            'email_sent': email_sent,
            'token': token,
        },
    )

    return {'email_sent': email_sent, 'token': token}
