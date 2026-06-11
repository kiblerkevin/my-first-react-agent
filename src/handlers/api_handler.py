"""Lambda handler: API Gateway request router.

Handles all dashboard API endpoints (public) and approval endpoints (protected).
Auth is enforced by the API Gateway authorizer; this handler reads the auth context.
"""

import json

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from src.shared.config import APPROVAL_EXPIRY_HOURS
from src.shared.dynamo_memory import DynamoMemory
from src.shared.secrets import get_secret
from tools.wordpress_publish_tool import WordPressPublishTool
from models.inputs.wordpress_publish_input import WordPressPublishInput

memory = DynamoMemory()
_serializer = None


def _get_serializer():
    global _serializer
    if _serializer is None:
        _serializer = URLSafeTimedSerializer(get_secret("APPROVAL_SECRET_KEY"))
    return _serializer


def handler(event, context):
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path = event.get("rawPath", "")
    query = event.get("queryStringParameters") or {}
    body = event.get("body", "")
    auth_context = event.get("requestContext", {}).get("authorizer", {}).get("lambda", {})

    # --- Dashboard API (public) ---
    if path == "/health":
        return _ok({"status": "ok"})

    if path == "/dashboard/api/runs":
        return _ok(memory.get_recent_runs(30))

    if path == "/dashboard/api/runs/window":
        offset = int(query.get("offset", 0))
        limit = int(query.get("limit", 7))
        total = memory.get_total_run_count()
        runs = memory.get_runs_in_window(offset, limit)
        return _ok({"runs": runs, "total": total, "offset": offset, "limit": limit})

    if path == "/dashboard/api/runs/range":
        start = query.get("start", "")
        end = query.get("end", "")
        if not start or not end:
            return _ok({"error": "start and end parameters required"}, 400)
        return _ok({"runs": memory.get_runs_in_range(start, end)})

    if path.startswith("/dashboard/api/iterations/"):
        run_id = path.split("/dashboard/api/iterations/", 1)[1]
        data = memory.get_run_iterations(run_id)
        if not data:
            return _ok({"error": "Run not found"}, 404)
        return _ok(data)

    if path == "/dashboard/api/evaluations":
        return _ok(memory.get_evaluation_trends(30))

    if path == "/dashboard/api/health":
        return _ok(memory.get_api_health(30))

    if path == "/dashboard/api/approvals":
        return _ok(memory.get_approval_stats(30))

    if path == "/dashboard/api/teams":
        return _ok(memory.get_team_coverage(30))

    if path == "/dashboard/api/sources":
        return _ok(memory.get_source_distribution(30))

    if path == "/dashboard/api/llm":
        return _ok(memory.get_llm_stats(30))

    if path == "/dashboard/api/cache":
        return _ok(memory.get_summary_cache_stats(30))

    if path == "/dashboard/api/drift":
        alerts = memory.get_active_drift_alerts()
        return _ok({"active_alerts": alerts, "count": len(alerts)})

    # --- Approval routes (protected) ---
    if path.startswith("/approve/"):
        return _handle_approve(path.split("/approve/", 1)[1])

    if path.startswith("/reject/"):
        token = path.split("/reject/", 1)[1]
        if method == "POST":
            return _handle_reject_post(token, body)
        return _handle_reject_get(token)

    if path.startswith("/status/"):
        return _handle_status(path.split("/status/", 1)[1])

    return _ok({"error": "Not found"}, 404)


def _handle_approve(token: str):
    serializer = _get_serializer()
    try:
        serializer.loads(token, salt="approval", max_age=APPROVAL_EXPIRY_HOURS * 3600)
    except (SignatureExpired, BadSignature):
        return _ok({"error": "Invalid or expired token"}, 404)

    approval = memory.get_pending_approval(token)
    if not approval:
        return _ok({"error": "Approval not found"}, 404)
    if approval.get("status") != "pending":
        return _ok({"error": "Already resolved", "status": approval["status"]})

    memory.update_approval_status(token, "approved")

    # Publish to WordPress
    try:
        taxonomy = json.loads(approval.get("taxonomy_data", "{}"))
        publish_tool = WordPressPublishTool()
        result = publish_tool.execute(WordPressPublishInput(
            title=approval["blog_title"],
            content=approval["blog_content"],
            excerpt=approval.get("blog_excerpt", ""),
            categories=taxonomy.get("categories", []),
            tags=taxonomy.get("tags", []),
        ))
        return _ok({"approved": True, "post_id": result.post_id, "post_url": result.post_url, "error": result.error})
    except Exception as e:
        return _ok({"approved": True, "publish_error": str(e)})


def _handle_reject_get(token: str):
    serializer = _get_serializer()
    try:
        serializer.loads(token, salt="approval", max_age=APPROVAL_EXPIRY_HOURS * 3600)
    except (SignatureExpired, BadSignature):
        return _ok({"error": "Invalid or expired token"}, 404)

    approval = memory.get_pending_approval(token)
    if not approval:
        return _ok({"error": "Approval not found"}, 404)
    if approval.get("status") != "pending":
        return _ok({"error": "Already resolved", "status": approval["status"]})

    return _ok({"token": token, "blog_title": approval["blog_title"], "status": "pending"})


def _handle_reject_post(token: str, body: str):
    serializer = _get_serializer()
    try:
        serializer.loads(token, salt="approval", max_age=APPROVAL_EXPIRY_HOURS * 3600)
    except (SignatureExpired, BadSignature):
        return _ok({"error": "Invalid or expired token"}, 404)

    approval = memory.get_pending_approval(token)
    if not approval:
        return _ok({"error": "Approval not found"}, 404)
    if approval.get("status") != "pending":
        return _ok({"error": "Already resolved", "status": approval["status"]})

    parsed_body = json.loads(body) if body else {}
    feedback = (parsed_body.get("feedback", "") or "").strip() or None
    memory.update_approval_status(token, "rejected", feedback=feedback)
    return _ok({"rejected": True, "feedback": feedback})


def _handle_status(token: str):
    approval = memory.get_pending_approval(token)
    if not approval:
        return _ok({"error": "Approval not found"}, 404)
    return _ok({
        "token": approval["token"],
        "status": approval.get("status"),
        "blog_title": approval.get("blog_title"),
        "created_at": approval.get("created_at"),
        "expires_at": approval.get("expires_at"),
        "resolved_at": approval.get("resolved_at"),
    })


def _ok(body, status_code=200):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        },
        "body": json.dumps(body, default=str),
    }
