"""Mixin for pending approval operations."""

from datetime import datetime
from typing import Any

from memory.database import PendingApproval, get_session
from utils.logger.logger import setup_logger

logger = setup_logger(__name__)


class ApprovalsMixin:
    """Pending approval database operations."""

    def create_pending_approval(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a pending approval."""
        session = get_session(self.engine)
        try:
            approval = PendingApproval(**data)
            session.add(approval)
            session.commit()
            logger.info(f'Created pending approval: {approval.token[:20]}...')
            return {
                'id': approval.id,
                'token': approval.token,
                'status': approval.status,
                'expires_at': approval.expires_at.isoformat(),
            }
        finally:
            session.close()

    def get_pending_approval(self, token: str) -> dict[str, Any] | None:
        """Get pending approval by token."""
        session = get_session(self.engine)
        try:
            approval = session.query(PendingApproval).filter_by(token=token).first()
            if not approval:
                return None
            return {
                'id': approval.id,
                'token': approval.token,
                'status': approval.status,
                'created_at': approval.created_at.isoformat(),
                'expires_at': approval.expires_at.isoformat(),
                'resolved_at': approval.resolved_at.isoformat()
                if approval.resolved_at
                else None,
                'blog_title': approval.blog_title,
                'blog_content': approval.blog_content,
                'blog_excerpt': approval.blog_excerpt,
                'taxonomy_data': approval.taxonomy_data,
                'evaluation_data': approval.evaluation_data,
                'summaries_data': approval.summaries_data,
                'scores_data': approval.scores_data,
                'feedback': approval.feedback,
            }
        finally:
            session.close()

    def update_approval_status(
        self, token: str, status: str, feedback: str | None = None
    ) -> None:
        """Update the status of a pending approval."""
        session = get_session(self.engine)
        try:
            approval = session.query(PendingApproval).filter_by(token=token).first()
            if approval:
                approval.status = status
                approval.resolved_at = datetime.utcnow()
                if feedback:
                    approval.feedback = feedback
                session.commit()
                logger.info(f'Updated approval {token[:20]}... to status={status}')
        finally:
            session.close()

    def get_expired_approvals(self) -> list[dict[str, Any]]:
        """Get expired pending approvals."""
        session = get_session(self.engine)
        try:
            expired = (
                session.query(PendingApproval)
                .filter(
                    PendingApproval.status == 'pending',
                    PendingApproval.expires_at < datetime.utcnow(),
                )
                .all()
            )
            return [{'token': a.token, 'blog_title': a.blog_title} for a in expired]
        finally:
            session.close()

    def get_most_recent_rejection(self) -> dict[str, Any] | None:
        """Get the most recent rejection feedback."""
        session = get_session(self.engine)
        try:
            approval = (
                session.query(PendingApproval)
                .filter(
                    PendingApproval.status == 'rejected',
                    PendingApproval.feedback.isnot(None),
                )
                .order_by(PendingApproval.resolved_at.desc())
                .first()
            )
            if not approval:
                return None
            return {'blog_title': approval.blog_title, 'feedback': approval.feedback}
        finally:
            session.close()

    def get_approval_stats(self, days: int = 30) -> dict[str, Any]:
        """Get approval statistics over the last days."""
        from datetime import timedelta

        session = get_session(self.engine)
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            approvals = (
                session.query(PendingApproval)
                .filter(PendingApproval.created_at >= cutoff)
                .all()
            )

            stats: dict[str, int] = {
                'approved': 0,
                'rejected': 0,
                'expired': 0,
                'pending': 0,
            }
            for a in approvals:
                stats[a.status] = stats.get(a.status, 0) + 1
            stats['total'] = len(approvals)
            return stats
        finally:
            session.close()
