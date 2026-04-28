"""Mixin for drift detection database operations."""

from datetime import datetime
from typing import Any

from memory.database import DriftAlert, PendingApproval, WorkflowRun, get_session
from utils.logger.logger import setup_logger

logger = setup_logger(__name__)


class DriftMixin:
    """Drift detection alert and metric operations."""

    def get_drift_metrics(self, window: int = 10) -> dict[str, Any]:
        """Get all data needed for drift detection in one query batch."""
        session = get_session(self.engine)
        try:
            runs = (
                session.query(WorkflowRun)
                .order_by(WorkflowRun.id.desc())
                .limit(window)
                .all()
            )

            approvals = (
                session.query(PendingApproval)
                .filter(PendingApproval.status.in_(['approved', 'rejected']))
                .order_by(PendingApproval.id.desc())
                .limit(window)
                .all()
            )

            return {
                'runs': [
                    {
                        'run_id': r.run_id,
                        'status': r.status,
                        'overall_score': r.overall_score,
                        'revision_tool_calls': r.revision_tool_calls,
                        'skip_reason': r.skip_reason,
                    }
                    for r in runs
                ],
                'approvals': [{'status': a.status} for a in approvals],
            }
        finally:
            session.close()

    def get_active_drift_alerts(self) -> list[dict[str, Any]]:
        """Get all currently active drift alerts."""
        session = get_session(self.engine)
        try:
            alerts = (
                session.query(DriftAlert).filter(DriftAlert.status == 'active').all()
            )
            return [
                {
                    'id': a.id,
                    'metric_name': a.metric_name,
                    'triggered_at': a.triggered_at.isoformat(),
                    'metric_value': a.metric_value,
                    'threshold': a.threshold,
                    'run_id': a.run_id,
                }
                for a in alerts
            ]
        finally:
            session.close()

    def create_drift_alert(
        self,
        metric_name: str,
        metric_value: float,
        threshold: float,
        run_id: str | None = None,
    ) -> int:
        """Create a new active drift alert."""
        session = get_session(self.engine)
        try:
            alert = DriftAlert(
                metric_name=metric_name,
                status='active',
                triggered_at=datetime.utcnow(),
                metric_value=metric_value,
                threshold=threshold,
                run_id=run_id,
            )
            session.add(alert)
            session.commit()
            logger.info(
                f'Drift alert created: {metric_name} '
                f'(value={metric_value}, threshold={threshold})'
            )
            return alert.id
        finally:
            session.close()

    def resolve_drift_alert(self, metric_name: str) -> None:
        """Resolve an active drift alert by metric name."""
        session = get_session(self.engine)
        try:
            alert = (
                session.query(DriftAlert)
                .filter(
                    DriftAlert.metric_name == metric_name, DriftAlert.status == 'active'
                )
                .first()
            )
            if alert:
                alert.status = 'resolved'
                alert.resolved_at = datetime.utcnow()
                session.commit()
                logger.info(f'Drift alert resolved: {metric_name}')
        finally:
            session.close()

    def has_active_alert(self, metric_name: str) -> bool:
        """Check if a metric already has an active alert (for suppression)."""
        session = get_session(self.engine)
        try:
            return (
                session.query(DriftAlert)
                .filter(
                    DriftAlert.metric_name == metric_name, DriftAlert.status == 'active'
                )
                .count()
                > 0
            )
        finally:
            session.close()
