"""Flask approval server with OAuth, approval routes, dashboard, and scheduler."""

import json
import os
import sys
import time
from typing import Any

import bleach
import yaml
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template_string, request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.memory import Memory
from models.inputs.wordpress_publish_input import WordPressPublishInput
from server.dashboard import dashboard_bp
from tools.wordpress_publish_tool import WordPressPublishTool
from utils.logger.logger import setup_logger

load_dotenv()
logger = setup_logger(__name__)

SCHEDULER_CONFIG_PATH = 'config/scheduler.yaml'
ORCHESTRATION_CONFIG_PATH = 'config/orchestration.yaml'

app = Flask(__name__)
app.register_blueprint(dashboard_bp)
memory = Memory()


@app.after_request
def _set_security_headers(response: Any) -> Any:
    """Add security headers to all responses."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Content-Security-Policy'] = "default-src 'self'"
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response


WP_CLIENT_ID = os.getenv('WORDPRESS_CLIENT_ID')
WP_CLIENT_SECRET = os.getenv('WORDPRESS_CLIENT_SECRET')
WP_REDIRECT_URI = (
    os.getenv('APPROVAL_BASE_URL', 'http://localhost:5000') + '/oauth/callback'
)
WP_AUTHORIZE_URL = 'https://public-api.wordpress.com/oauth2/authorize'
WP_TOKEN_URL = 'https://public-api.wordpress.com/oauth2/token'


# --- HTML Templates ---

APPROVED_PAGE = """
<html><body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
<h1 style="color: #28a745;">✅ Blog Post Approved</h1>
<p><strong>{{ title }}</strong> has been approved and will be published shortly.</p>
{{ post_info|safe }}
</body></html>
"""

ALREADY_RESOLVED_PAGE = """
<html><body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
<h1 style="color: #6c757d;">Already Resolved</h1>
<p>This approval request has already been <strong>{{ status }}</strong>.</p>
</body></html>
"""

INVALID_TOKEN_PAGE = """
<html><body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
<h1 style="color: #dc3545;">Invalid Token</h1>
<p>This approval link is invalid or has expired.</p>
</body></html>
"""

REJECT_FORM_PAGE = """
<html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 50px;">
<h1 style="color: #dc3545;">❌ Reject Blog Post</h1>
<p><strong>{{ title }}</strong></p>
<form method="POST">
    <label for="feedback"><strong>Feedback (optional):</strong></label><br>
    <textarea name="feedback" id="feedback" rows="6"
              style="width: 100%; margin: 10px 0; padding: 10px; font-size: 14px;"
              placeholder="What should be improved?"></textarea><br>
    <button type="submit"
            style="background-color: #dc3545; color: white; padding: 12px 30px;
                   border: none; border-radius: 5px; font-size: 16px; cursor: pointer;">
        Confirm Rejection
    </button>
</form>
</body></html>
"""

REJECTED_PAGE = """
<html><body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
<h1 style="color: #dc3545;">❌ Blog Post Rejected</h1>
<p><strong>{{ title }}</strong> has been rejected and archived.</p>
{% if feedback %}<p><strong>Feedback:</strong> {{ feedback }}</p>{% endif %}
</body></html>
"""

STATUS_PAGE = """
<html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 50px;">
<h1>Approval Status</h1>
<p><strong>Title:</strong> {{ approval.blog_title }}</p>
<p><strong>Status:</strong> {{ approval.status }}</p>
<p><strong>Created:</strong> {{ approval.created_at }}</p>
<p><strong>Expires:</strong> {{ approval.expires_at }}</p>
{% if approval.resolved_at %}<p><strong>Resolved:</strong> {{ approval.resolved_at }}</p>{% endif %}
{% if approval.feedback %}<p><strong>Feedback:</strong> {{ approval.feedback }}</p>{% endif %}
</body></html>
"""

OAUTH_SUCCESS_PAGE = """
<html><body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
<h1 style="color: #28a745;">✅ WordPress Authorized</h1>
<p>OAuth token saved. The approval server can now publish to WordPress.</p>
<p><strong>Blog:</strong> {{ blog_url }}</p>
</body></html>
"""

OAUTH_ERROR_PAGE = """
<html><body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
<h1 style="color: #dc3545;">OAuth Error</h1>
<p>{{ error }}</p>
</body></html>
"""


@app.route('/health')
def health() -> Any:
    """Return service health status."""
    return jsonify({'status': 'ok'})


# --- OAuth Routes ---


@app.route('/oauth/start')
def oauth_start() -> Any:
    """Redirect to WordPress OAuth authorization page."""
    params = {
        'client_id': WP_CLIENT_ID,
        'redirect_uri': WP_REDIRECT_URI,
        'response_type': 'code',
        'scope': 'global',
    }
    auth_url = f'{WP_AUTHORIZE_URL}?' + '&'.join(f'{k}={v}' for k, v in params.items())
    return redirect(auth_url)


@app.route('/oauth/callback')
def oauth_callback() -> Any:
    """Handle WordPress OAuth callback and store the access token."""
    code = request.args.get('code')
    error = request.args.get('error')

    if error:
        return render_template_string(OAUTH_ERROR_PAGE, error=error), 400

    if not code:
        return (
            render_template_string(
                OAUTH_ERROR_PAGE, error='No authorization code received.'
            ),
            400,
        )

    try:
        import requests as req

        response = req.post(
            WP_TOKEN_URL,
            data={
                'client_id': WP_CLIENT_ID,
                'client_secret': WP_CLIENT_SECRET,
                'redirect_uri': WP_REDIRECT_URI,
                'code': code,
                'grant_type': 'authorization_code',
            },
        )
        response.raise_for_status()
        data = response.json()

        access_token = data.get('access_token')
        blog_id = str(data.get('blog_id', ''))
        blog_url = data.get('blog_url', '')

        memory.save_oauth_token(
            'wordpress', access_token, blog_id=blog_id, blog_url=blog_url
        )
        logger.info(f'WordPress OAuth token saved for blog: {blog_url}')

        return render_template_string(OAUTH_SUCCESS_PAGE, blog_url=blog_url)

    except Exception as e:
        logger.error(f'OAuth callback error: {e}')
        return render_template_string(
            OAUTH_ERROR_PAGE,
            error='An internal error occurred during authorization. Please try again.',
        ), 500


# --- Approval Routes ---


@app.route('/approve/<token>')
def approve(token: str) -> Any:
    """Approve a blog post and trigger WordPress publish."""
    approval = memory.get_pending_approval(token)
    if not approval:
        return render_template_string(INVALID_TOKEN_PAGE), 404

    if approval['status'] != 'pending':
        return render_template_string(ALREADY_RESOLVED_PAGE, status=approval['status'])

    memory.update_approval_status(token, 'approved')
    logger.info(f'Blog post approved: {approval["blog_title"]}')

    publish_result = None
    try:
        taxonomy: dict[str, Any] = json.loads(approval.get('taxonomy_data', '{}'))
        publish_tool = WordPressPublishTool()
        publish_result = publish_tool.execute(
            WordPressPublishInput(
                title=approval['blog_title'],
                content=approval['blog_content'],
                excerpt=approval.get('blog_excerpt', ''),
                categories=taxonomy.get('categories', []),
                tags=taxonomy.get('tags', []),
            )
        )
        if publish_result.error:
            logger.error(f'WordPress publish error: {publish_result.error}')
        else:
            logger.info(f'Published to WordPress: post_id={publish_result.post_id}')
            from memory.database import WorkflowRun as WR
            from memory.database import get_session

            session = get_session(memory.engine)
            last_run = (
                session.query(WR)
                .filter_by(status='success')
                .order_by(WR.id.desc())
                .first()
            )
            if last_run:
                memory.update_workflow_publish_result(
                    last_run.run_id,
                    publish_result.post_id,
                    publish_result.post_url,
                    True,
                )
            session.close()
    except Exception as e:
        logger.error(f'Error triggering WordPress publish: {e}')

    title = approval['blog_title']
    post_info = ''
    if publish_result and publish_result.post_id:
        post_info = (
            f'<p>WordPress draft created: '
            f"<a href='{publish_result.post_url}'>{publish_result.post_url}</a></p>"
        )
    elif (
        publish_result
        and publish_result.error
        and 'oauth' in publish_result.error.lower()
    ):
        post_info = (
            "<p style='color: #dc3545;'><strong>WordPress publish failed:</strong> "
            'OAuth token is invalid or revoked. '
            "<a href='/oauth/start'>Re-authorize WordPress</a> and try again.</p>"
        )
    elif publish_result and publish_result.error:
        post_info = (
            f"<p style='color: #dc3545;'><strong>WordPress publish failed:</strong> "
            f'{publish_result.error}</p>'
        )

    return render_template_string(
        APPROVED_PAGE,
        title=title,
        post_info=bleach.clean(
            post_info,
            tags=['p', 'a', 'strong'],
            attributes={'a': ['href']},
        ),
    )


@app.route('/reject/<token>', methods=['GET', 'POST'])
def reject(token: str) -> Any:
    """Show rejection form (GET) or process rejection with feedback (POST)."""
    approval = memory.get_pending_approval(token)
    if not approval:
        return render_template_string(INVALID_TOKEN_PAGE), 404

    if approval['status'] != 'pending':
        return render_template_string(ALREADY_RESOLVED_PAGE, status=approval['status'])

    if request.method == 'GET':
        return render_template_string(REJECT_FORM_PAGE, title=approval['blog_title'])

    feedback: str | None = request.form.get('feedback', '').strip() or None
    memory.update_approval_status(token, 'rejected', feedback=feedback)
    logger.info(f'Blog post rejected: {approval["blog_title"]} (feedback: {feedback})')

    return render_template_string(
        REJECTED_PAGE, title=approval['blog_title'], feedback=feedback
    )


@app.route('/status/<token>')
def status(token: str) -> Any:
    """Show the current status of an approval request."""
    approval = memory.get_pending_approval(token)
    if not approval:
        return render_template_string(INVALID_TOKEN_PAGE), 404

    return render_template_string(STATUS_PAGE, approval=approval)


# --- Background Jobs ---


def check_expired_approvals() -> None:
    """Auto-archive any pending approvals that have passed their expiry time."""
    expired = memory.get_expired_approvals()
    for approval in expired:
        memory.update_approval_status(approval['token'], 'expired')
        logger.info(f'Auto-archived expired approval: {approval["blog_title"]}')
    if expired:
        logger.info(f'Archived {len(expired)} expired approval(s).')


def run_scheduled_workflow() -> None:
    """Run the daily workflow with exponential backoff retry."""
    with open(SCHEDULER_CONFIG_PATH, 'r') as f:
        config: dict[str, Any] = yaml.safe_load(f)

    max_retries: int = config['retry']['max_retries']
    base_delay: float = config['retry']['base_delay_seconds']
    max_articles_per_team: int = config['daily_workflow']['max_articles_per_team']

    from workflow.daily_workflow import run_daily_workflow

    failed_run_id: str | None = None

    for attempt in range(max_retries):
        try:
            logger.info(f'Daily workflow attempt {attempt + 1}/{max_retries}')
            result: dict[str, Any] = run_daily_workflow(
                max_articles_per_team=max_articles_per_team,
                resume_run_id=failed_run_id,
            )

            if result.get('skipped'):
                logger.info(
                    f'Daily workflow skipped (run_id={result.get("run_id")}): '
                    f'{result.get("skip_reason")}'
                )
                return

            logger.info(
                f'Daily workflow completed (run_id={result.get("run_id")}): '
                f"'{result['title']}' | score={result['overall_score']}/10 | "
                f'email_sent={result["email_sent"]}'
            )
            return
        except Exception as e:
            delay = base_delay * (2**attempt)
            if not failed_run_id:
                from memory.database import WorkflowRun, get_session

                session = get_session(memory.engine)
                last_run = (
                    session.query(WorkflowRun)
                    .filter_by(status='failed')
                    .order_by(WorkflowRun.id.desc())
                    .first()
                )
                if last_run:
                    failed_run_id = last_run.run_id
                session.close()
            logger.error(
                f'Daily workflow failed (attempt {attempt + 1}/{max_retries}): {e} | '
                f'resume_run_id={failed_run_id} | retrying in {delay}s...'
            )
            if attempt < max_retries - 1:
                time.sleep(delay)

    logger.error(f'Daily workflow failed after {max_retries} attempts. Skipping today.')


def start_scheduler() -> None:
    """Start the APScheduler with expiry checker and daily workflow jobs."""
    with open(SCHEDULER_CONFIG_PATH, 'r') as f:
        config: dict[str, Any] = yaml.safe_load(f)

    executors = {'default': ThreadPoolExecutor(20)}
    scheduler = BackgroundScheduler(executors=executors)

    expiry_interval: int = config['expiry_checker']['interval_minutes']
    scheduler.add_job(
        check_expired_approvals,
        'interval',
        minutes=expiry_interval,
        misfire_grace_time=3600,
    )
    logger.info(f'Expiry checker started (interval: {expiry_interval} minutes)')

    wf: dict[str, Any] = config['daily_workflow']
    scheduler.add_job(
        run_scheduled_workflow,
        CronTrigger(
            hour=wf['cron_hour'],
            minute=wf['cron_minute'],
            timezone=wf['timezone'],
        ),
        misfire_grace_time=3600,
    )
    logger.info(
        f'Daily workflow scheduled at {wf["cron_hour"]}:{wf["cron_minute"]:02d} '
        f'{wf["timezone"]}'
    )

    scheduler.start()


# --- Entry Point ---

if __name__ == '__main__':
    start_scheduler()
    port = int(os.getenv('APPROVAL_BASE_URL', 'http://localhost:5000').split(':')[-1])
    host = os.getenv('APPROVAL_BIND_HOST', '127.0.0.1')
    logger.info(f'Approval server starting on {host}:{port}')
    app.run(host=host, port=port, debug=False)
