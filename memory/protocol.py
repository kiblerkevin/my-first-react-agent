"""Abstract Memory Protocol defining the interface for all persistence operations.

Any backend (SQLite, DynamoDB, etc.) must implement this protocol.
Tools and workflow code depend on this interface, not concrete implementations.
"""

from abc import ABC, abstractmethod
from typing import Any


class MemoryProtocol(ABC):
    """Abstract interface for all persistent memory operations."""

    # --- Articles ---

    @abstractmethod
    def get_seen_urls(self) -> set[str]:
        """Get all article URLs previously stored."""

    @abstractmethod
    def save_articles(self, articles: list[dict[str, Any]]) -> None:
        """Persist a list of articles."""

    @abstractmethod
    def purge_old_articles(self) -> None:
        """Remove articles older than the retention period."""

    @abstractmethod
    def get_article_summary(self, url: str) -> dict[str, Any] | None:
        """Get a cached article summary by URL."""

    @abstractmethod
    def save_article_summary(self, data: dict[str, Any]) -> None:
        """Save an article summary."""

    # --- Workflow ---

    @abstractmethod
    def create_workflow_run(self, run_id: str) -> str:
        """Create a new workflow run. Returns an identifier."""

    @abstractmethod
    def update_workflow_run(self, run_id: str, data: dict[str, Any]) -> None:
        """Update a workflow run with new data."""

    @abstractmethod
    def get_workflow_run_db_id(self, run_id: str) -> str | None:
        """Get the database identifier for a workflow run."""

    @abstractmethod
    def save_checkpoint(
        self, run_id: str, step_name: str, data: dict[str, Any]
    ) -> None:
        """Save checkpoint data for a workflow step."""

    @abstractmethod
    def get_checkpoint(self, run_id: str) -> dict[str, Any] | None:
        """Get checkpoint data for a workflow run."""

    @abstractmethod
    def save_api_call_result(
        self,
        workflow_run_id: str,
        source_name: str,
        status: str,
        article_count: int | None = None,
        error: str | None = None,
    ) -> None:
        """Save the result of an API call for a workflow run."""

    @abstractmethod
    def save_summary_stats(
        self, workflow_run_id: str, stats: list[dict[str, Any]]
    ) -> None:
        """Save per-team summarization statistics for a workflow run."""

    @abstractmethod
    def save_blog_draft(self, data: dict[str, Any]) -> str:
        """Save a blog draft. Returns the draft identifier."""

    @abstractmethod
    def save_evaluation(self, summary_id: str, evaluation: dict[str, Any]) -> None:
        """Save evaluation scores for a blog draft."""

    @abstractmethod
    def update_workflow_revision_metrics(
        self,
        run_id: str,
        tool_calls: int,
        draft_attempts: int,
        score_progression: list[float],
        draft_iterations: list[dict[str, Any]] | None = None,
    ) -> None:
        """Update revision metrics for a workflow run."""

    @abstractmethod
    def update_workflow_publish_result(
        self, run_id: str, post_id: int, post_url: str, success: bool
    ) -> None:
        """Update the publish result for a workflow run."""

    # --- Approvals ---

    @abstractmethod
    def create_pending_approval(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a pending approval record."""

    @abstractmethod
    def get_pending_approval(self, token: str) -> dict[str, Any] | None:
        """Get a pending approval by token."""

    @abstractmethod
    def update_approval_status(
        self, token: str, status: str, feedback: str | None = None
    ) -> None:
        """Update the status of a pending approval."""

    @abstractmethod
    def get_expired_approvals(self) -> list[dict[str, Any]]:
        """Get all expired pending approvals."""

    @abstractmethod
    def get_most_recent_rejection(self) -> dict[str, Any] | None:
        """Get the most recent rejection with feedback."""

    # --- Taxonomy ---

    @abstractmethod
    def get_or_create_category(self, name: str) -> dict[str, Any]:
        """Get or create a category by name."""

    @abstractmethod
    def get_or_create_tag(self, name: str) -> dict[str, Any]:
        """Get or create a tag by name."""

    @abstractmethod
    def get_all_categories(self) -> list[dict[str, Any]]:
        """Get all categories."""

    @abstractmethod
    def get_all_tags(self) -> list[dict[str, Any]]:
        """Get all tags."""

    @abstractmethod
    def update_category_wordpress_id(self, name: str, wordpress_id: int) -> None:
        """Update the WordPress ID for a category."""

    @abstractmethod
    def update_tag_wordpress_id(self, name: str, wordpress_id: int) -> None:
        """Update the WordPress ID for a tag."""

    # --- Drift ---

    @abstractmethod
    def get_drift_metrics(self, window: int = 10) -> dict[str, Any]:
        """Get data needed for drift detection."""

    @abstractmethod
    def get_active_drift_alerts(self) -> list[dict[str, Any]]:
        """Get all currently active drift alerts."""

    @abstractmethod
    def create_drift_alert(
        self,
        metric_name: str,
        metric_value: float,
        threshold: float,
        run_id: str | None = None,
    ) -> str:
        """Create a new active drift alert. Returns alert identifier."""

    @abstractmethod
    def resolve_drift_alert(self, metric_name: str) -> None:
        """Resolve an active drift alert by metric name."""

    @abstractmethod
    def has_active_alert(self, metric_name: str) -> bool:
        """Check if a metric already has an active alert."""

    # --- Dashboard Queries ---

    @abstractmethod
    def get_recent_runs(self, limit: int = 30) -> list[dict[str, Any]]:
        """Get recent workflow runs."""

    @abstractmethod
    def get_evaluation_trends(self, days: int = 30) -> list[dict[str, Any]]:
        """Get evaluation score trends over time."""

    @abstractmethod
    def get_api_health(self, days: int = 30) -> list[dict[str, Any]]:
        """Get API call health metrics."""

    @abstractmethod
    def get_team_coverage(self, days: int = 30) -> dict[str, int]:
        """Get article count per team."""

    @abstractmethod
    def get_source_distribution(self, days: int = 30) -> dict[str, int]:
        """Get article count per source."""

    @abstractmethod
    def get_summary_cache_stats(self, days: int = 30) -> dict[str, Any]:
        """Get summarization cache hit/miss statistics."""

    @abstractmethod
    def get_llm_stats(self, days: int = 30) -> dict[str, Any]:
        """Get LLM usage statistics."""

    @abstractmethod
    def get_run_iterations(self, run_id: str) -> dict[str, Any] | None:
        """Get draft iterations and evaluations for a specific run."""

    @abstractmethod
    def get_runs_in_window(self, offset: int, limit: int) -> list[dict[str, Any]]:
        """Get workflow runs in a paginated window."""

    @abstractmethod
    def get_runs_in_range(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Get workflow runs within a date range."""

    @abstractmethod
    def get_total_run_count(self) -> int:
        """Get total number of workflow runs."""

    @abstractmethod
    def get_approval_stats(self, days: int = 30) -> dict[str, Any]:
        """Get approval statistics over the given period."""

    # --- Backup/Housekeeping ---

    @abstractmethod
    def purge_old_logs(self) -> None:
        """Purge old log files or records."""

    @abstractmethod
    def backup_database(self) -> None:
        """Create a database backup (no-op for managed services)."""

    @abstractmethod
    def purge_old_backups(self) -> None:
        """Remove old backups beyond retention period (no-op for managed services)."""
