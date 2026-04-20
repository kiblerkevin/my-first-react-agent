"""Tool for sending approval emails and standalone failure notification emails."""

import json
import os
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import yaml
from dotenv import load_dotenv
from itsdangerous import URLSafeTimedSerializer

from memory.memory import Memory
from models.inputs.send_approval_email_input import SendApprovalEmailInput
from models.outputs.send_approval_email_output import SendApprovalEmailOutput
from tools.base_tool import BaseTool
from utils.logger.logger import setup_logger

logger = setup_logger(__name__)

load_dotenv()

ORCHESTRATION_CONFIG_PATH = 'config/orchestration.yaml'


class SendApprovalEmailTool(BaseTool):
    """Sends an HTML approval email with approve/reject buttons."""

    model_config = {'arbitrary_types_allowed': True, 'extra': 'allow'}

    input_model: type = SendApprovalEmailInput

    name: str = 'send_approval_email'
    description: str = (
        'Sends an approval email with the blog post draft for human review. '
        'The email includes rendered HTML content, evaluation scores, and taxonomy. '
        'Approve/reject buttons link to the approval server. '
        'The post auto-archives after 24 hours if no action is taken.'
    )
    input_schema: dict[str, Any] = {
        'type': 'object',
        'properties': {
            'title': {'type': 'string'},
            'content': {'type': 'string'},
            'excerpt': {'type': 'string'},
            'categories': {'type': 'array', 'items': {'type': 'object'}},
            'tags': {'type': 'array', 'items': {'type': 'object'}},
            'evaluation_scores': {'type': 'object'},
            'summaries': {'type': 'array', 'items': {'type': 'object'}},
            'scores': {'type': 'array', 'items': {'type': 'object'}},
        },
        'required': ['title', 'content'],
    }
    output_schema: dict[str, Any] = {
        'type': 'object',
        'properties': {
            'token': {'type': 'string'},
            'expires_at': {'type': 'string'},
            'email_sent': {'type': 'boolean'},
            'error': {'type': 'string'},
        },
    }

    def __init__(self) -> None:
        """Initialize with approval config, email credentials, and memory."""
        super().__init__(
            name=self.model_fields['name'].default,
            description=self.model_fields['description'].default,
            input_schema=self.model_fields['input_schema'].default,
            output_schema=self.model_fields['output_schema'].default,
        )
        with open(ORCHESTRATION_CONFIG_PATH, 'r') as f:
            config = yaml.safe_load(f)
        self.expiry_hours: int = config['approval']['expiry_hours']
        self.memory = Memory()

        self.secret_key: str | None = os.getenv('APPROVAL_SECRET_KEY')
        self.base_url: str | None = os.getenv('APPROVAL_BASE_URL')
        self.smtp_server: str | None = os.getenv('EMAIL_SMTP_SERVER')
        self.smtp_port: int = int(os.getenv('EMAIL_SMTP_PORT', '587'))
        self.email_from: str | None = os.getenv('EMAIL_FROM')
        self.email_password: str | None = os.getenv('EMAIL_PASSWORD')
        self.email_to: str | None = os.getenv('EMAIL_TO')

        self.serializer = URLSafeTimedSerializer(self.secret_key)

    def execute(self, input: SendApprovalEmailInput) -> SendApprovalEmailOutput:
        """Generate a signed token, persist approval, and send the email.

        Args:
            input: Blog post data, taxonomy, and evaluation scores.

        Returns:
            Output with token, expiry, and send status.
        """
        token: str = self.serializer.dumps(input.title, salt='approval')
        expires_at = datetime.now(timezone.utc) + timedelta(hours=self.expiry_hours)

        self.memory.create_pending_approval(
            {
                'token': token,
                'status': 'pending',
                'expires_at': expires_at,
                'blog_title': input.title,
                'blog_content': input.content,
                'blog_excerpt': input.excerpt,
                'taxonomy_data': json.dumps(
                    {
                        'categories': input.categories,
                        'tags': input.tags,
                    }
                ),
                'evaluation_data': json.dumps(input.evaluation_scores),
                'summaries_data': json.dumps(input.summaries),
                'scores_data': json.dumps(input.scores),
            }
        )

        try:
            email_html = self._build_email(input, token, expires_at)
            self._send_email(input.title, email_html)
            logger.info(
                f"Approval email sent for '{input.title}', token={token[:20]}..."
            )
            return SendApprovalEmailOutput(
                token=token,
                expires_at=expires_at.isoformat(),
                email_sent=True,
            )
        except Exception as e:
            logger.error(f'Failed to send approval email: {e}')
            return SendApprovalEmailOutput(
                token=token,
                expires_at=expires_at.isoformat(),
                email_sent=False,
                error=str(e),
            )

    def _build_email(
        self,
        input: SendApprovalEmailInput,
        token: str,
        expires_at: datetime,
    ) -> str:
        """Build the approval email HTML body.

        Args:
            input: Blog post data and metadata.
            token: Signed approval token.
            expires_at: Token expiry datetime.

        Returns:
            Rendered HTML email string.
        """
        approve_url = f'{self.base_url}/approve/{token}'
        reject_url = f'{self.base_url}/reject/{token}'

        scores_html = ''
        if input.evaluation_scores:
            scores_html = "<h2>Evaluation Scores</h2><table border='1' cellpadding='8' cellspacing='0'>"
            for criterion, score in input.evaluation_scores.items():
                scores_html += (
                    f'<tr><td><strong>{criterion}</strong></td><td>{score}/10</td></tr>'
                )
            scores_html += '</table>'

        categories_html = (
            ', '.join(c.get('name', '') for c in input.categories)
            if input.categories
            else 'None'
        )
        tags_html = (
            ', '.join(t.get('name', '') for t in input.tags) if input.tags else 'None'
        )

        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto;">
            <h1>Blog Post Approval Request</h1>
            <p><strong>Title:</strong> {input.title}</p>
            <p><strong>Excerpt:</strong> {input.excerpt}</p>
            <p><strong>Categories:</strong> {categories_html}</p>
            <p><strong>Tags:</strong> {tags_html}</p>
            <p><strong>Expires:</strong> {expires_at.strftime('%B %d, %Y at %I:%M %p UTC')}</p>

            {scores_html}

            <h2>Blog Post Preview</h2>
            <div style="border: 1px solid #ccc; padding: 20px; margin: 10px 0; background: #fafafa;">
                {input.content}
            </div>

            <div style="margin: 30px 0; text-align: center;">
                <a href="{approve_url}"
                   style="background-color: #28a745; color: white; padding: 15px 40px;
                          text-decoration: none; border-radius: 5px; font-size: 18px;
                          margin-right: 20px; display: inline-block;">
                    ✅ Approve & Publish
                </a>
                <a href="{reject_url}"
                   style="background-color: #dc3545; color: white; padding: 15px 40px;
                          text-decoration: none; border-radius: 5px; font-size: 18px;
                          display: inline-block;">
                    ❌ Reject
                </a>
            </div>

            <p style="color: #666; font-size: 12px;">
                This approval request expires in {self.expiry_hours} hours.
                If no action is taken, the post will be auto-archived.
            </p>
        </body>
        </html>
        """

    def _send_email(
        self,
        subject: str,
        html_content: str,
        recipient: str | None = None,
    ) -> None:
        """Send an HTML email via SMTP.

        Args:
            subject: Email subject line.
            html_content: HTML body content.
            recipient: Override recipient address.
        """
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'[Approval Required] {subject}'
        msg['From'] = self.email_from or ''
        msg['To'] = recipient or self.email_to or ''
        msg.attach(MIMEText(html_content, 'html'))

        with smtplib.SMTP(self.smtp_server or '', self.smtp_port) as server:
            server.starttls()
            server.login(self.email_from or '', self.email_password or '')
            server.sendmail(
                self.email_from or '',
                recipient or self.email_to or '',
                msg.as_string(),
            )


def send_failure_email(
    run_id: str,
    error: str,
    steps_completed: list[str],
    context: dict[str, Any] | None = None,
) -> None:
    """Send a failure notification email when the workflow fails.

    Standalone function — not a tool, not agent-callable.

    Args:
        run_id: Workflow run identifier.
        error: Error message from the failure.
        steps_completed: List of step names that completed before failure.
        context: Optional partial data to include in the email.
    """
    load_dotenv()

    with open(ORCHESTRATION_CONFIG_PATH, 'r') as f:
        config = yaml.safe_load(f)

    if not config.get('failure_notification', {}).get('enabled', False):
        logger.info('Failure notification disabled — skipping email.')
        return

    smtp_server = os.getenv('EMAIL_SMTP_SERVER')
    smtp_port = int(os.getenv('EMAIL_SMTP_PORT', '587'))
    email_from = os.getenv('EMAIL_FROM')
    email_password = os.getenv('EMAIL_PASSWORD')
    error_email_to = os.getenv('ERROR_EMAIL_TO', os.getenv('EMAIL_TO'))

    timestamp = datetime.now(timezone.utc).strftime('%B %d, %Y at %I:%M %p UTC')

    all_steps = [
        'fetch_scores',
        'fetch_articles',
        'deduplicate_articles',
        'summarize_articles',
        'draft_and_evaluate',
        'create_taxonomy',
        'send_approval_email',
    ]
    failed_step = 'unknown'
    for step in all_steps:
        if step not in steps_completed:
            failed_step = step
            break

    context_html = ''
    if context:
        context_html = (
            "<h2>Partial Data</h2><table border='1' cellpadding='8' cellspacing='0'>"
        )
        for key, value in context.items():
            context_html += f'<tr><td><strong>{key}</strong></td><td>{value}</td></tr>'
        context_html += '</table>'

    steps_html = ''
    for step in all_steps:
        if step in steps_completed:
            steps_html += f'<tr><td>✅</td><td>{step}</td></tr>'
        elif step == failed_step:
            steps_html += (
                f'<tr><td>❌</td><td><strong>{step}</strong> (failed)</td></tr>'
            )
        else:
            steps_html += f'<tr><td>⏭️</td><td>{step} (skipped)</td></tr>'

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto;">
        <h1 style="color: #dc3545;">⚠️ Workflow Failed</h1>
        <p><strong>Run ID:</strong> {run_id}</p>
        <p><strong>Time:</strong> {timestamp}</p>
        <p><strong>Failed at step:</strong> {failed_step}</p>

        <h2>Error</h2>
        <pre style="background: #f8f9fa; padding: 15px; border-radius: 5px; overflow-x: auto;">{error}</pre>

        <h2>Steps</h2>
        <table border='1' cellpadding='8' cellspacing='0'>
            <tr><th>Status</th><th>Step</th></tr>
            {steps_html}
        </table>

        {context_html}

        <p style="color: #666; font-size: 12px; margin-top: 30px;">
            To resume this run: <code>python main.py --resume {run_id}</code>
        </p>
    </body>
    </html>
    """

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'[Workflow Failed] Chicago Sports Recap — {failed_step}'
        msg['From'] = email_from or ''
        msg['To'] = error_email_to or ''
        msg.attach(MIMEText(html, 'html'))

        with smtplib.SMTP(smtp_server or '', smtp_port) as server:
            server.starttls()
            server.login(email_from or '', email_password or '')
            server.sendmail(email_from or '', error_email_to or '', msg.as_string())

        logger.info(f'Failure notification sent to {error_email_to} for run {run_id}')
    except Exception as e:
        logger.error(f'Failed to send failure notification email: {e}')
