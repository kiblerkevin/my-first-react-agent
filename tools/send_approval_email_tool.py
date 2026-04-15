import json
import os
import smtplib
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import yaml
from dotenv import load_dotenv
from itsdangerous import URLSafeTimedSerializer

from tools.base_tool import BaseTool
from models.inputs.send_approval_email_input import SendApprovalEmailInput
from models.outputs.send_approval_email_output import SendApprovalEmailOutput
from memory.memory import Memory
from utils.logger.logger import setup_logger


logger = setup_logger(__name__)

load_dotenv()

ORCHESTRATION_CONFIG_PATH = 'config/orchestration.yaml'


class SendApprovalEmailTool(BaseTool):
    model_config = {"arbitrary_types_allowed": True, "extra": "allow"}

    input_model: type = SendApprovalEmailInput

    name: str = "send_approval_email"
    description: str = (
        "Sends an approval email with the blog post draft for human review. "
        "The email includes rendered HTML content, evaluation scores, and taxonomy. "
        "Approve/reject buttons link to the approval server. "
        "The post auto-archives after 24 hours if no action is taken."
    )
    input_schema: dict = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "content": {"type": "string"},
            "excerpt": {"type": "string"},
            "categories": {"type": "array", "items": {"type": "object"}},
            "tags": {"type": "array", "items": {"type": "object"}},
            "evaluation_scores": {"type": "object"},
            "summaries": {"type": "array", "items": {"type": "object"}},
            "scores": {"type": "array", "items": {"type": "object"}}
        },
        "required": ["title", "content"]
    }
    output_schema: dict = {
        "type": "object",
        "properties": {
            "token": {"type": "string"},
            "expires_at": {"type": "string"},
            "email_sent": {"type": "boolean"},
            "error": {"type": "string"}
        }
    }

    def __init__(self):
        super().__init__(
            name=self.model_fields['name'].default,
            description=self.model_fields['description'].default,
            input_schema=self.model_fields['input_schema'].default,
            output_schema=self.model_fields['output_schema'].default
        )
        with open(ORCHESTRATION_CONFIG_PATH, 'r') as f:
            config = yaml.safe_load(f)
        self.expiry_hours = config['approval']['expiry_hours']
        self.memory = Memory()

        self.secret_key = os.getenv('APPROVAL_SECRET_KEY')
        self.base_url = os.getenv('APPROVAL_BASE_URL')
        self.smtp_server = os.getenv('EMAIL_SMTP_SERVER')
        self.smtp_port = int(os.getenv('EMAIL_SMTP_PORT', 587))
        self.email_from = os.getenv('EMAIL_FROM')
        self.email_password = os.getenv('EMAIL_PASSWORD')
        self.email_to = os.getenv('EMAIL_TO')

        self.serializer = URLSafeTimedSerializer(self.secret_key)

    def execute(self, input: SendApprovalEmailInput) -> SendApprovalEmailOutput:
        token = self.serializer.dumps(input.title, salt='approval')
        expires_at = datetime.now(timezone.utc) + timedelta(hours=self.expiry_hours)

        self.memory.create_pending_approval({
            'token': token,
            'status': 'pending',
            'expires_at': expires_at,
            'blog_title': input.title,
            'blog_content': input.content,
            'blog_excerpt': input.excerpt,
            'taxonomy_data': json.dumps({
                'categories': input.categories,
                'tags': input.tags
            }),
            'evaluation_data': json.dumps(input.evaluation_scores),
            'summaries_data': json.dumps(input.summaries),
            'scores_data': json.dumps(input.scores)
        })

        try:
            email_html = self._build_email(input, token, expires_at)
            self._send_email(input.title, email_html)
            logger.info(f"Approval email sent for '{input.title}', token={token[:20]}...")
            return SendApprovalEmailOutput(
                token=token,
                expires_at=expires_at.isoformat(),
                email_sent=True
            )
        except Exception as e:
            logger.error(f"Failed to send approval email: {e}")
            return SendApprovalEmailOutput(
                token=token,
                expires_at=expires_at.isoformat(),
                email_sent=False,
                error=str(e)
            )

    def _build_email(self, input: SendApprovalEmailInput, token: str, expires_at: datetime) -> str:
        approve_url = f"{self.base_url}/approve/{token}"
        reject_url = f"{self.base_url}/reject/{token}"

        scores_html = ""
        if input.evaluation_scores:
            scores_html = "<h2>Evaluation Scores</h2><table border='1' cellpadding='8' cellspacing='0'>"
            for criterion, score in input.evaluation_scores.items():
                scores_html += f"<tr><td><strong>{criterion}</strong></td><td>{score}/10</td></tr>"
            scores_html += "</table>"

        categories_html = ", ".join(c.get('name', '') for c in input.categories) if input.categories else "None"
        tags_html = ", ".join(t.get('name', '') for t in input.tags) if input.tags else "None"

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

    def _send_email(self, subject: str, html_content: str):
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"[Approval Required] {subject}"
        msg['From'] = self.email_from
        msg['To'] = self.email_to
        msg.attach(MIMEText(html_content, 'html'))

        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            server.starttls()
            server.login(self.email_from, self.email_password)
            server.sendmail(self.email_from, self.email_to, msg.as_string())
