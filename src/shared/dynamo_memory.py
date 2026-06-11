"""DynamoDB implementation of MemoryProtocol for Lambda.

Uses boto3 DynamoDB resource with module-level caching for warm starts.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import boto3

from memory.protocol import MemoryProtocol
from src.shared.config import (
    TABLE_API_CALL_RESULTS,
    TABLE_ARTICLE_SUMMARIES,
    TABLE_ARTICLES,
    TABLE_CATEGORIES,
    TABLE_DRIFT_ALERTS,
    TABLE_EVALUATIONS,
    TABLE_IMPROVEMENT_SUGGESTIONS,
    TABLE_PENDING_APPROVALS,
    TABLE_SUMMARIES,
    TABLE_SUMMARY_STATS,
    TABLE_SUMMARY_TAGS,
    TABLE_TAGS,
    TABLE_WORKFLOW_RUNS,
)

_dynamodb = None


def _get_dynamodb():
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb")
    return _dynamodb


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decimal_to_native(obj):
    """Recursively convert Decimal to int/float for JSON compatibility."""
    if isinstance(obj, Decimal):
        return int(obj) if obj == int(obj) else float(obj)
    if isinstance(obj, dict):
        return {k: _decimal_to_native(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimal_to_native(i) for i in obj]
    return obj


def _clean_item(item: dict) -> dict:
    """Remove None values and convert Decimals from a DynamoDB item."""
    return _decimal_to_native({k: v for k, v in item.items() if v is not None})


class DynamoMemory(MemoryProtocol):
    """DynamoDB-backed memory implementation."""

    def __init__(self):
        self._db = _get_dynamodb()

    def _table(self, name: str):
        return self._db.Table(name)

    # --- Articles ---

    def get_seen_urls(self) -> set[str]:
        table = self._table(TABLE_ARTICLES)
        response = table.scan(ProjectionExpression="url")
        urls = {item["url"] for item in response.get("Items", [])}
        while response.get("LastEvaluatedKey"):
            response = table.scan(
                ProjectionExpression="url",
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            urls.update(item["url"] for item in response.get("Items", []))
        return urls

    def save_articles(self, articles: list[dict[str, Any]]) -> None:
        table = self._table(TABLE_ARTICLES)
        with table.batch_writer() as batch:
            for article in articles:
                url = article.get("url")
                if not url:
                    continue
                batch.put_item(Item={
                    "url": url,
                    "title": article.get("title", ""),
                    "source": article.get("source", ""),
                    "team": article.get("team", ""),
                    "published_at": article.get("publishedAt", ""),
                    "fetched_at": _now_iso(),
                })

    def purge_old_articles(self) -> None:
        # DynamoDB TTL handles this automatically; no-op
        pass

    def get_article_summary(self, url: str) -> dict[str, Any] | None:
        table = self._table(TABLE_ARTICLE_SUMMARIES)
        response = table.get_item(Key={"url": url})
        item = response.get("Item")
        if not item:
            return None
        return _clean_item({
            "url": item["url"],
            "team": item.get("team"),
            "summary": item.get("summary", ""),
            "event_type": item.get("event_type"),
            "players_mentioned": item.get("players_mentioned", []),
            "is_relevant": item.get("is_relevant", True),
        })

    def save_article_summary(self, data: dict[str, Any]) -> None:
        table = self._table(TABLE_ARTICLE_SUMMARIES)
        players = data.get("players_mentioned", [])
        table.put_item(Item={
            "url": data.get("url", ""),
            "team": data.get("team", ""),
            "summary": data.get("summary", ""),
            "event_type": data.get("event_type", "other"),
            "players_mentioned": players if isinstance(players, list) else json.loads(players),
            "is_relevant": data.get("is_relevant", True),
            "created_at": _now_iso(),
        })

    # --- Workflow ---

    def create_workflow_run(self, run_id: str) -> str:
        table = self._table(TABLE_WORKFLOW_RUNS)
        table.put_item(Item={
            "run_id": run_id,
            "started_at": _now_iso(),
            "status": "running",
        })
        return run_id

    def update_workflow_run(self, run_id: str, data: dict[str, Any]) -> None:
        table = self._table(TABLE_WORKFLOW_RUNS)
        update_parts = ["#completed_at = :completed_at", "#status = :status"]
        names = {"#completed_at": "completed_at", "#status": "status"}
        values: dict[str, Any] = {":completed_at": _now_iso(), ":status": data.get("status", "unknown")}

        optional_fields = [
            "skip_reason", "error", "scores_fetched", "articles_fetched",
            "articles_new", "summaries_count", "overall_score", "email_sent",
            "total_input_tokens", "total_output_tokens", "estimated_cost",
        ]
        for field in optional_fields:
            if data.get(field) is not None:
                update_parts.append(f"#{field} = :{field}")
                names[f"#{field}"] = field
                values[f":{field}"] = data[field]

        if data.get("steps_completed") is not None:
            update_parts.append("#steps_completed = :steps_completed")
            names["#steps_completed"] = "steps_completed"
            values[":steps_completed"] = data["steps_completed"]

        if data.get("usage_by_tool") is not None:
            update_parts.append("#usage_by_tool = :usage_by_tool")
            names["#usage_by_tool"] = "usage_by_tool"
            values[":usage_by_tool"] = data["usage_by_tool"]

        table.update_item(
            Key={"run_id": run_id},
            UpdateExpression="SET " + ", ".join(update_parts),
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )

    def get_workflow_run_db_id(self, run_id: str) -> str | None:
        table = self._table(TABLE_WORKFLOW_RUNS)
        response = table.get_item(Key={"run_id": run_id}, ProjectionExpression="run_id")
        return run_id if response.get("Item") else None

    def save_checkpoint(self, run_id: str, step_name: str, data: dict[str, Any]) -> None:
        table = self._table(TABLE_WORKFLOW_RUNS)
        # Read current checkpoint, merge, write back
        response = table.get_item(Key={"run_id": run_id}, ProjectionExpression="checkpoint_data")
        existing = response.get("Item", {}).get("checkpoint_data", {})
        if isinstance(existing, str):
            existing = json.loads(existing)
        existing[step_name] = data
        table.update_item(
            Key={"run_id": run_id},
            UpdateExpression="SET #cp = :cp",
            ExpressionAttributeNames={"#cp": "checkpoint_data"},
            ExpressionAttributeValues={":cp": json.dumps(existing, default=str)},
        )

    def get_checkpoint(self, run_id: str) -> dict[str, Any] | None:
        table = self._table(TABLE_WORKFLOW_RUNS)
        response = table.get_item(Key={"run_id": run_id})
        item = response.get("Item")
        if not item:
            return None
        cp_data = item.get("checkpoint_data")
        if not cp_data:
            return None
        if isinstance(cp_data, str):
            cp_data = json.loads(cp_data)
        steps = item.get("steps_completed", [])
        if isinstance(steps, str):
            steps = json.loads(steps)
        return {"steps_completed": steps, "data": cp_data}

    def save_api_call_result(
        self,
        workflow_run_id: str,
        source_name: str,
        status: str,
        article_count: int | None = None,
        error: str | None = None,
    ) -> None:
        table = self._table(TABLE_API_CALL_RESULTS)
        item: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "workflow_run_id": workflow_run_id,
            "source_name": source_name,
            "status": status,
            "created_at": _now_iso(),
        }
        if article_count is not None:
            item["article_count"] = article_count
        if error:
            item["error_message"] = error
        table.put_item(Item=item)

    def save_summary_stats(self, workflow_run_id: str, stats: list[dict[str, Any]]) -> None:
        table = self._table(TABLE_SUMMARY_STATS)
        with table.batch_writer() as batch:
            for s in stats:
                batch.put_item(Item={
                    "id": str(uuid.uuid4()),
                    "workflow_run_id": workflow_run_id,
                    "team": s.get("team", ""),
                    "articles_fetched": s.get("articles_fetched", 0),
                    "articles_summarized": s.get("articles_summarized", 0),
                    "cache_hits": s.get("cache_hits", 0),
                    "cache_misses": s.get("cache_misses", 0),
                })

    def save_blog_draft(self, data: dict[str, Any]) -> str:
        table = self._table(TABLE_SUMMARIES)
        summary_id = str(uuid.uuid4())
        teams = data.get("teams_covered", [])
        table.put_item(Item={
            "id": summary_id,
            "created_at": _now_iso(),
            "title": data.get("title", ""),
            "html_content": data.get("content", ""),
            "summary": data.get("excerpt", ""),
            "teams_covered": json.dumps(teams) if isinstance(teams, list) else teams,
            "article_count": data.get("article_count", 0),
            "overall_score": Decimal(str(data.get("overall_score", 0))),
        })
        return summary_id

    def save_evaluation(self, summary_id: str, evaluation: dict[str, Any]) -> None:
        table = self._table(TABLE_EVALUATIONS)
        evaluation_id = evaluation.get("evaluation_id", "")
        criteria_scores = evaluation.get("criteria_scores", {})
        criteria_reasoning = evaluation.get("criteria_reasoning", {})
        with table.batch_writer() as batch:
            for criterion, score in criteria_scores.items():
                batch.put_item(Item={
                    "id": str(uuid.uuid4()),
                    "evaluation_id": evaluation_id,
                    "summary_id": summary_id,
                    "criterion": criterion,
                    "score": Decimal(str(score)),
                    "reasoning": criteria_reasoning.get(criterion, ""),
                })

    def update_workflow_revision_metrics(
        self,
        run_id: str,
        tool_calls: int,
        draft_attempts: int,
        score_progression: list[float],
        draft_iterations: list[dict[str, Any]] | None = None,
    ) -> None:
        table = self._table(TABLE_WORKFLOW_RUNS)
        update_expr = "SET #rtc = :rtc, #da = :da, #sp = :sp"
        names = {"#rtc": "revision_tool_calls", "#da": "draft_attempts", "#sp": "score_progression"}
        values: dict[str, Any] = {
            ":rtc": tool_calls,
            ":da": draft_attempts,
            ":sp": json.dumps(score_progression),
        }
        if draft_iterations:
            update_expr += ", #di = :di"
            names["#di"] = "draft_iterations"
            values[":di"] = json.dumps(draft_iterations, default=str)
        table.update_item(
            Key={"run_id": run_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )

    def update_workflow_publish_result(
        self, run_id: str, post_id: int, post_url: str, success: bool
    ) -> None:
        table = self._table(TABLE_WORKFLOW_RUNS)
        table.update_item(
            Key={"run_id": run_id},
            UpdateExpression="SET #pid = :pid, #purl = :purl, #ps = :ps",
            ExpressionAttributeNames={"#pid": "publish_post_id", "#purl": "publish_post_url", "#ps": "publish_success"},
            ExpressionAttributeValues={":pid": post_id, ":purl": post_url, ":ps": success},
        )

    # --- Approvals ---

    def create_pending_approval(self, data: dict[str, Any]) -> dict[str, Any]:
        table = self._table(TABLE_PENDING_APPROVALS)
        expires_at = data.get("expires_at")
        if hasattr(expires_at, "isoformat"):
            expires_at = expires_at.isoformat()
        item = {
            "token": data["token"],
            "status": data.get("status", "pending"),
            "created_at": _now_iso(),
            "expires_at": expires_at or "",
            "blog_title": data["blog_title"],
            "blog_content": data["blog_content"],
            "blog_excerpt": data.get("blog_excerpt", ""),
            "taxonomy_data": data.get("taxonomy_data", "{}"),
            "evaluation_data": data.get("evaluation_data", "{}"),
            "summaries_data": data.get("summaries_data", "[]"),
            "scores_data": data.get("scores_data", "[]"),
        }
        table.put_item(Item=item)
        return {"token": item["token"], "status": item["status"], "expires_at": item["expires_at"]}

    def get_pending_approval(self, token: str) -> dict[str, Any] | None:
        table = self._table(TABLE_PENDING_APPROVALS)
        response = table.get_item(Key={"token": token})
        item = response.get("Item")
        if not item:
            return None
        return _clean_item(item)

    def update_approval_status(
        self, token: str, status: str, feedback: str | None = None
    ) -> None:
        table = self._table(TABLE_PENDING_APPROVALS)
        update_expr = "SET #status = :status, #resolved_at = :resolved_at"
        names = {"#status": "status", "#resolved_at": "resolved_at"}
        values: dict[str, Any] = {":status": status, ":resolved_at": _now_iso()}
        if feedback:
            update_expr += ", #feedback = :feedback"
            names["#feedback"] = "feedback"
            values[":feedback"] = feedback
        table.update_item(
            Key={"token": token},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )

    def get_expired_approvals(self) -> list[dict[str, Any]]:
        table = self._table(TABLE_PENDING_APPROVALS)
        now = _now_iso()
        response = table.query(
            IndexName="status-created_at-index",
            KeyConditionExpression="#s = :s",
            FilterExpression="#e < :now",
            ExpressionAttributeNames={"#s": "status", "#e": "expires_at"},
            ExpressionAttributeValues={":s": "pending", ":now": now},
        )
        return [{"token": i["token"], "blog_title": i.get("blog_title", "")} for i in response.get("Items", [])]

    def get_most_recent_rejection(self) -> dict[str, Any] | None:
        table = self._table(TABLE_PENDING_APPROVALS)
        response = table.query(
            IndexName="status-created_at-index",
            KeyConditionExpression="#s = :s",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": "rejected"},
            ScanIndexForward=False,
            Limit=1,
        )
        items = response.get("Items", [])
        if not items:
            return None
        item = items[0]
        feedback = item.get("feedback")
        if not feedback:
            return None
        return {"blog_title": item.get("blog_title", ""), "feedback": feedback}

    # --- Taxonomy ---

    def get_or_create_category(self, name: str) -> dict[str, Any]:
        table = self._table(TABLE_CATEGORIES)
        # Try GSI lookup by name
        response = table.query(
            IndexName="name-index",
            KeyConditionExpression="#n = :n",
            ExpressionAttributeNames={"#n": "name"},
            ExpressionAttributeValues={":n": name},
            Limit=1,
        )
        items = response.get("Items", [])
        if items:
            return _clean_item({"id": items[0]["id"], "name": items[0]["name"], "wordpress_id": items[0].get("wordpress_id")})
        cat_id = str(uuid.uuid4())
        table.put_item(Item={"id": cat_id, "name": name})
        return {"id": cat_id, "name": name, "wordpress_id": None}

    def get_or_create_tag(self, name: str) -> dict[str, Any]:
        table = self._table(TABLE_TAGS)
        response = table.query(
            IndexName="name-index",
            KeyConditionExpression="#n = :n",
            ExpressionAttributeNames={"#n": "name"},
            ExpressionAttributeValues={":n": name},
            Limit=1,
        )
        items = response.get("Items", [])
        if items:
            return _clean_item({"id": items[0]["id"], "name": items[0]["name"], "wordpress_id": items[0].get("wordpress_id")})
        tag_id = str(uuid.uuid4())
        table.put_item(Item={"id": tag_id, "name": name})
        return {"id": tag_id, "name": name, "wordpress_id": None}

    def get_all_categories(self) -> list[dict[str, Any]]:
        table = self._table(TABLE_CATEGORIES)
        response = table.scan()
        return [_clean_item({"id": i["id"], "name": i["name"], "wordpress_id": i.get("wordpress_id")}) for i in response.get("Items", [])]

    def get_all_tags(self) -> list[dict[str, Any]]:
        table = self._table(TABLE_TAGS)
        response = table.scan()
        return [_clean_item({"id": i["id"], "name": i["name"], "wordpress_id": i.get("wordpress_id")}) for i in response.get("Items", [])]

    def update_category_wordpress_id(self, name: str, wordpress_id: int) -> None:
        cat = self.get_or_create_category(name)
        table = self._table(TABLE_CATEGORIES)
        table.update_item(
            Key={"id": cat["id"]},
            UpdateExpression="SET #wp = :wp",
            ExpressionAttributeNames={"#wp": "wordpress_id"},
            ExpressionAttributeValues={":wp": wordpress_id},
        )

    def update_tag_wordpress_id(self, name: str, wordpress_id: int) -> None:
        tag = self.get_or_create_tag(name)
        table = self._table(TABLE_TAGS)
        table.update_item(
            Key={"id": tag["id"]},
            UpdateExpression="SET #wp = :wp",
            ExpressionAttributeNames={"#wp": "wordpress_id"},
            ExpressionAttributeValues={":wp": wordpress_id},
        )

    # --- Drift ---

    def get_drift_metrics(self, window: int = 10) -> dict[str, Any]:
        table = self._table(TABLE_WORKFLOW_RUNS)
        response = table.query(
            IndexName="status-started_at-index",
            KeyConditionExpression="#s = :s",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": "success"},
            ScanIndexForward=False,
            Limit=window,
        )
        runs = [_clean_item(i) for i in response.get("Items", [])]

        approvals_table = self._table(TABLE_PENDING_APPROVALS)
        approved = approvals_table.query(
            IndexName="status-created_at-index",
            KeyConditionExpression="#s = :s",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": "approved"},
            ScanIndexForward=False,
            Limit=window,
        ).get("Items", [])
        rejected = approvals_table.query(
            IndexName="status-created_at-index",
            KeyConditionExpression="#s = :s",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": "rejected"},
            ScanIndexForward=False,
            Limit=window,
        ).get("Items", [])

        approvals = [{"status": "approved"} for _ in approved] + [{"status": "rejected"} for _ in rejected]
        return {"runs": runs, "approvals": approvals}

    def get_active_drift_alerts(self) -> list[dict[str, Any]]:
        table = self._table(TABLE_DRIFT_ALERTS)
        response = table.query(
            IndexName="status-triggered_at-index",
            KeyConditionExpression="#s = :s",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": "active"},
        )
        return [_clean_item(i) for i in response.get("Items", [])]

    def create_drift_alert(
        self,
        metric_name: str,
        metric_value: float,
        threshold: float,
        run_id: str | None = None,
    ) -> str:
        table = self._table(TABLE_DRIFT_ALERTS)
        alert_id = str(uuid.uuid4())
        item: dict[str, Any] = {
            "id": alert_id,
            "metric_name": metric_name,
            "status": "active",
            "triggered_at": _now_iso(),
            "metric_value": Decimal(str(metric_value)),
            "threshold": Decimal(str(threshold)),
        }
        if run_id:
            item["run_id"] = run_id
        table.put_item(Item=item)
        return alert_id

    def resolve_drift_alert(self, metric_name: str) -> None:
        # Find active alert by metric_name, then update
        alerts = self.get_active_drift_alerts()
        table = self._table(TABLE_DRIFT_ALERTS)
        for alert in alerts:
            if alert.get("metric_name") == metric_name:
                table.update_item(
                    Key={"id": alert["id"]},
                    UpdateExpression="SET #s = :s, #r = :r",
                    ExpressionAttributeNames={"#s": "status", "#r": "resolved_at"},
                    ExpressionAttributeValues={":s": "resolved", ":r": _now_iso()},
                )
                break

    def has_active_alert(self, metric_name: str) -> bool:
        alerts = self.get_active_drift_alerts()
        return any(a.get("metric_name") == metric_name for a in alerts)

    # --- Dashboard Queries ---

    def get_recent_runs(self, limit: int = 30) -> list[dict[str, Any]]:
        table = self._table(TABLE_WORKFLOW_RUNS)
        # Scan and sort client-side (acceptable for small dataset)
        response = table.scan()
        items = [_clean_item(i) for i in response.get("Items", [])]
        items.sort(key=lambda x: x.get("started_at", ""), reverse=True)
        return items[:limit]

    def get_evaluation_trends(self, days: int = 30) -> list[dict[str, Any]]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        table = self._table(TABLE_EVALUATIONS)
        response = table.scan()
        items = [_clean_item(i) for i in response.get("Items", [])]
        # Join with summaries to get created_at
        summaries_table = self._table(TABLE_SUMMARIES)
        summaries_resp = summaries_table.scan(ProjectionExpression="id, created_at")
        summary_dates = {i["id"]: i.get("created_at", "") for i in summaries_resp.get("Items", [])}
        results = []
        for item in items:
            created_at = summary_dates.get(item.get("summary_id", ""), "")
            if created_at >= cutoff:
                item["created_at"] = created_at
                results.append(item)
        return results

    def get_api_health(self, days: int = 30) -> list[dict[str, Any]]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        table = self._table(TABLE_API_CALL_RESULTS)
        response = table.scan()
        return [_clean_item(i) for i in response.get("Items", []) if i.get("created_at", "") >= cutoff]

    def get_team_coverage(self, days: int = 30) -> dict[str, int]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        table = self._table(TABLE_ARTICLES)
        response = table.scan(ProjectionExpression="team, fetched_at")
        counts: dict[str, int] = {}
        for item in response.get("Items", []):
            if item.get("fetched_at", "") >= cutoff:
                team = item.get("team", "Unknown")
                counts[team] = counts.get(team, 0) + 1
        return counts

    def get_source_distribution(self, days: int = 30) -> dict[str, int]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        table = self._table(TABLE_ARTICLES)
        response = table.scan(ProjectionExpression="source, fetched_at")
        counts: dict[str, int] = {}
        for item in response.get("Items", []):
            if item.get("fetched_at", "") >= cutoff:
                source = item.get("source", "Unknown")
                counts[source] = counts.get(source, 0) + 1
        return counts

    def get_summary_cache_stats(self, days: int = 30) -> dict[str, Any]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        table = self._table(TABLE_SUMMARY_STATS)
        response = table.scan()
        total_hits = 0
        total_misses = 0
        for item in response.get("Items", []):
            total_hits += int(item.get("cache_hits", 0))
            total_misses += int(item.get("cache_misses", 0))
        total = total_hits + total_misses
        return {
            "cache_hits": total_hits,
            "cache_misses": total_misses,
            "hit_rate": round(total_hits / total * 100, 1) if total > 0 else 0,
        }

    def get_llm_stats(self, days: int = 30) -> dict[str, Any]:
        runs = self.get_recent_runs(limit=100)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        filtered = [r for r in runs if r.get("started_at", "") >= cutoff]
        total_input = sum(r.get("total_input_tokens", 0) for r in filtered)
        total_output = sum(r.get("total_output_tokens", 0) for r in filtered)
        total_cost = sum(r.get("estimated_cost", 0) for r in filtered)
        return {
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "estimated_cost": round(total_cost, 4),
            "run_count": len(filtered),
        }

    def get_run_iterations(self, run_id: str) -> dict[str, Any] | None:
        table = self._table(TABLE_WORKFLOW_RUNS)
        response = table.get_item(Key={"run_id": run_id})
        item = response.get("Item")
        if not item:
            return None
        result = _clean_item(item)
        # Parse JSON fields
        for field in ("draft_iterations", "score_progression", "steps_completed"):
            val = result.get(field)
            if isinstance(val, str):
                result[field] = json.loads(val)
        return result

    def get_runs_in_window(self, offset: int, limit: int) -> list[dict[str, Any]]:
        runs = self.get_recent_runs(limit=offset + limit)
        return runs[offset:offset + limit]

    def get_runs_in_range(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        runs = self.get_recent_runs(limit=1000)
        return [r for r in runs if start_date <= r.get("started_at", "") <= end_date]

    def get_total_run_count(self) -> int:
        table = self._table(TABLE_WORKFLOW_RUNS)
        response = table.scan(Select="COUNT")
        return response.get("Count", 0)

    def get_approval_stats(self, days: int = 30) -> dict[str, Any]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        table = self._table(TABLE_PENDING_APPROVALS)
        response = table.scan()
        stats: dict[str, int] = {"approved": 0, "rejected": 0, "expired": 0, "pending": 0}
        for item in response.get("Items", []):
            if item.get("created_at", "") >= cutoff:
                status = item.get("status", "pending")
                stats[status] = stats.get(status, 0) + 1
        stats["total"] = sum(stats.values())
        return stats

    # --- Backup/Housekeeping ---

    def purge_old_logs(self) -> None:
        # CloudWatch handles log retention in Lambda; no-op
        pass

    def backup_database(self) -> None:
        # DynamoDB PITR handles backups; no-op
        pass

    def purge_old_backups(self) -> None:
        # No local backups in Lambda; no-op
        pass
