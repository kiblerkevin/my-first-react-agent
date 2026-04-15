import os
import sys
import json

import yaml
from flask import Flask, request, render_template_string, redirect
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

# Add project root to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.memory import Memory
from tools.wordpress_publish_tool import WordPressPublishTool
from models.inputs.wordpress_publish_input import WordPressPublishInput
from utils.logger.logger import setup_logger


load_dotenv()
logger = setup_logger(__name__)

ORCHESTRATION_CONFIG_PATH = 'config/orchestration.yaml'

app = Flask(__name__)
memory = Memory()

WP_CLIENT_ID = os.getenv('WORDPRESS_CLIENT_ID')
WP_CLIENT_SECRET = os.getenv('WORDPRESS_CLIENT_SECRET')
WP_REDIRECT_URI = os.getenv('APPROVAL_BASE_URL', 'http://localhost:5000') + '/oauth/callback'
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


# --- OAuth Routes ---

@app.route('/oauth/start')
def oauth_start():
    params = {
        'client_id': WP_CLIENT_ID,
        'redirect_uri': WP_REDIRECT_URI,
        'response_type': 'code',
        'scope': 'global'
    }
    auth_url = f"{WP_AUTHORIZE_URL}?" + "&".join(f"{k}={v}" for k, v in params.items())
    return redirect(auth_url)


@app.route('/oauth/callback')
def oauth_callback():
    code = request.args.get('code')
    error = request.args.get('error')

    if error:
        return render_template_string(OAUTH_ERROR_PAGE, error=error), 400

    if not code:
        return render_template_string(OAUTH_ERROR_PAGE, error='No authorization code received.'), 400

    try:
        import requests as req
        response = req.post(WP_TOKEN_URL, data={
            'client_id': WP_CLIENT_ID,
            'client_secret': WP_CLIENT_SECRET,
            'redirect_uri': WP_REDIRECT_URI,
            'code': code,
            'grant_type': 'authorization_code'
        })
        response.raise_for_status()
        data = response.json()

        access_token = data.get('access_token')
        blog_id = str(data.get('blog_id', ''))
        blog_url = data.get('blog_url', '')

        memory.save_oauth_token('wordpress', access_token, blog_id=blog_id, blog_url=blog_url)
        logger.info(f"WordPress OAuth token saved for blog: {blog_url}")

        return render_template_string(OAUTH_SUCCESS_PAGE, blog_url=blog_url)

    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        return render_template_string(OAUTH_ERROR_PAGE, error=str(e)), 500


# --- Approval Routes ---

@app.route('/approve/<token>')
def approve(token):
    approval = memory.get_pending_approval(token)
    if not approval:
        return render_template_string(INVALID_TOKEN_PAGE), 404

    if approval['status'] != 'pending':
        return render_template_string(ALREADY_RESOLVED_PAGE, status=approval['status'])

    memory.update_approval_status(token, 'approved')
    logger.info(f"Blog post approved: {approval['blog_title']}")

    # Trigger WordPress publish
    publish_result = None
    try:
        taxonomy = json.loads(approval.get('taxonomy_data', '{}'))
        publish_tool = WordPressPublishTool()
        publish_result = publish_tool.execute(WordPressPublishInput(
            title=approval['blog_title'],
            content=approval['blog_content'],
            excerpt=approval.get('blog_excerpt', ''),
            categories=taxonomy.get('categories', []),
            tags=taxonomy.get('tags', [])
        ))
        if publish_result.error:
            logger.error(f"WordPress publish error: {publish_result.error}")
        else:
            logger.info(f"Published to WordPress: post_id={publish_result.post_id}")
    except Exception as e:
        logger.error(f"Error triggering WordPress publish: {e}")

    title = approval['blog_title']
    post_info = ""
    if publish_result and publish_result.post_id:
        post_info = f"<p>WordPress draft created: <a href='{publish_result.post_url}'>{publish_result.post_url}</a></p>"

    return render_template_string(APPROVED_PAGE, title=title, post_info=post_info)


@app.route('/reject/<token>', methods=['GET', 'POST'])
def reject(token):
    approval = memory.get_pending_approval(token)
    if not approval:
        return render_template_string(INVALID_TOKEN_PAGE), 404

    if approval['status'] != 'pending':
        return render_template_string(ALREADY_RESOLVED_PAGE, status=approval['status'])

    if request.method == 'GET':
        return render_template_string(REJECT_FORM_PAGE, title=approval['blog_title'])

    feedback = request.form.get('feedback', '').strip() or None
    memory.update_approval_status(token, 'rejected', feedback=feedback)
    logger.info(f"Blog post rejected: {approval['blog_title']} (feedback: {feedback})")

    return render_template_string(REJECTED_PAGE, title=approval['blog_title'], feedback=feedback)


@app.route('/status/<token>')
def status(token):
    approval = memory.get_pending_approval(token)
    if not approval:
        return render_template_string(INVALID_TOKEN_PAGE), 404

    return render_template_string(STATUS_PAGE, approval=approval)


# --- Background Scheduler ---

def check_expired_approvals():
    expired = memory.get_expired_approvals()
    for approval in expired:
        memory.update_approval_status(approval['token'], 'expired')
        logger.info(f"Auto-archived expired approval: {approval['blog_title']}")
    if expired:
        logger.info(f"Archived {len(expired)} expired approval(s).")


def start_scheduler():
    with open(ORCHESTRATION_CONFIG_PATH, 'r') as f:
        config = yaml.safe_load(f)
    interval = config['approval']['check_interval_minutes']

    scheduler = BackgroundScheduler()
    scheduler.add_job(check_expired_approvals, 'interval', minutes=interval)
    scheduler.start()
    logger.info(f"Expiry checker started (interval: {interval} minutes)")


# --- Entry Point ---

if __name__ == '__main__':
    start_scheduler()
    port = int(os.getenv('APPROVAL_BASE_URL', 'http://localhost:5000').split(':')[-1])
    logger.info(f"Approval server starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
