"""Mixin for workflow run tracking and checkpoint operations."""

import json as _json
from datetime import datetime
from typing import Any

from memory.database import (
    ApiCallResult,
    Evaluation,
    Summary,
    SummaryStats,
    WorkflowRun,
    get_session,
)
from utils.logger.logger import setup_logger

logger = setup_logger(__name__)


class WorkflowMixin:
    """Workflow run, checkpoint, and revision metric operations."""

    def save_blog_draft(self, data: dict[str, Any]) -> int:
        """Save a blog draft."""
        session = get_session(self.engine)
        try:
            draft = Summary(
                title=data.get('title', ''),
                html_content=data.get('content', ''),
                summary=data.get('excerpt', ''),
                teams_covered=_json.dumps(data.get('teams_covered', [])),
                article_count=data.get('article_count', 0),
                overall_score=data.get('overall_score'),
            )
            session.add(draft)
            session.commit()
            logger.info(f"Saved blog draft: '{data.get('title', '')}' (id={draft.id})")
            return draft.id
        finally:
            session.close()

    def save_evaluation(self, summary_id: int, evaluation: dict[str, Any]) -> None:
        """Save an evaluation for a summary."""
        session = get_session(self.engine)
        try:
            evaluation_id = evaluation.get('evaluation_id', '')
            criteria_scores = evaluation.get('criteria_scores', {})
            criteria_reasoning = evaluation.get('criteria_reasoning', {})

            for criterion, score in criteria_scores.items():
                session.add(
                    Evaluation(
                        evaluation_id=evaluation_id,
                        summary_id=summary_id,
                        criterion=criterion,
                        score=float(score),
                        reasoning=criteria_reasoning.get(criterion),
                    )
                )
            session.commit()
            logger.info(
                f'Saved evaluation {evaluation_id[:20]}... '
                f'({len(criteria_scores)} criteria) for summary_id={summary_id}'
            )
        finally:
            session.close()

    def create_workflow_run(self, run_id: str) -> int:
        """Create a new workflow run."""
        session = get_session(self.engine)
        try:
            run = WorkflowRun(
                run_id=run_id, started_at=datetime.utcnow(), status='running'
            )
            session.add(run)
            session.commit()
            logger.info(f'Workflow run started: {run_id}')
            return run.id
        finally:
            session.close()

    def update_workflow_run(self, run_id: str, data: dict[str, Any]) -> None:
        """Update a workflow run with new data."""
        session = get_session(self.engine)
        try:
            run = session.query(WorkflowRun).filter_by(run_id=run_id).first()
            if not run:
                return
            run.completed_at = datetime.utcnow()
            run.status = data.get('status', run.status)
            run.skip_reason = data.get('skip_reason')
            run.error = data.get('error')
            run.steps_completed = _json.dumps(data.get('steps_completed', []))
            run.scores_fetched = data.get('scores_fetched')
            run.articles_fetched = data.get('articles_fetched')
            run.articles_new = data.get('articles_new')
            run.summaries_count = data.get('summaries_count')
            run.overall_score = data.get('overall_score')
            run.email_sent = data.get('email_sent')
            run.total_input_tokens = data.get('total_input_tokens')
            run.total_output_tokens = data.get('total_output_tokens')
            run.estimated_cost = data.get('estimated_cost')
            if data.get('usage_by_tool'):
                run.usage_by_tool = _json.dumps(data['usage_by_tool'])
            session.commit()
            logger.info(f'Workflow run updated: {run_id} -> {data.get("status")}')
        finally:
            session.close()

    def save_checkpoint(
        self, run_id: str, step_name: str, data: dict[str, Any]
    ) -> None:
        """Save a checkpoint for a workflow run."""
        session = get_session(self.engine)
        try:
            run = session.query(WorkflowRun).filter_by(run_id=run_id).first()
            if not run:
                return
            checkpoint = _json.loads(run.checkpoint_data) if run.checkpoint_data else {}
            checkpoint[step_name] = data
            run.checkpoint_data = _json.dumps(checkpoint)
            session.commit()
        finally:
            session.close()

    def get_checkpoint(self, run_id: str) -> dict[str, Any] | None:
        """Get the checkpoint data for a workflow run."""
        session = get_session(self.engine)
        try:
            run = session.query(WorkflowRun).filter_by(run_id=run_id).first()
            if not run or not run.checkpoint_data:
                return None
            return {
                'steps_completed': _json.loads(run.steps_completed)
                if run.steps_completed
                else [],
                'data': _json.loads(run.checkpoint_data),
            }
        finally:
            session.close()

    def get_workflow_run_db_id(self, run_id: str) -> int | None:
        """Get the database ID for a workflow run."""
        session = get_session(self.engine)
        try:
            run = session.query(WorkflowRun).filter_by(run_id=run_id).first()
            return run.id if run else None
        finally:
            session.close()

    def save_api_call_result(
        self,
        workflow_run_id: int,
        source_name: str,
        status: str,
        article_count: int | None = None,
        error: str | None = None,
    ) -> None:
        """Save the result of an API call."""
        session = get_session(self.engine)
        try:
            session.add(
                ApiCallResult(
                    workflow_run_id=workflow_run_id,
                    source_name=source_name,
                    status=status,
                    article_count=article_count,
                    error_message=error,
                )
            )
            session.commit()
        finally:
            session.close()

    def save_summary_stats(
        self, workflow_run_id: int, stats: list[dict[str, Any]]
    ) -> None:
        """Save summary statistics for a workflow run."""
        session = get_session(self.engine)
        try:
            for s in stats:
                session.add(
                    SummaryStats(
                        workflow_run_id=workflow_run_id,
                        team=s.get('team', ''),
                        articles_fetched=s.get('articles_fetched', 0),
                        articles_summarized=s.get('articles_summarized', 0),
                        cache_hits=s.get('cache_hits', 0),
                        cache_misses=s.get('cache_misses', 0),
                    )
                )
            session.commit()
        finally:
            session.close()

    def update_workflow_publish_result(
        self, run_id: str, post_id: int, post_url: str, success: bool
    ) -> None:
        """Update the publish result for a workflow run."""
        session = get_session(self.engine)
        try:
            run = session.query(WorkflowRun).filter_by(run_id=run_id).first()
            if run:
                run.publish_post_id = post_id
                run.publish_post_url = post_url
                run.publish_success = success
                session.commit()
        finally:
            session.close()

    def update_workflow_revision_metrics(
        self,
        run_id: str,
        tool_calls: int,
        draft_attempts: int,
        score_progression: list[float],
        draft_iterations: list[dict[str, Any]] | None = None,
    ) -> None:
        """Update revision metrics for a workflow run."""
        session = get_session(self.engine)
        try:
            run = session.query(WorkflowRun).filter_by(run_id=run_id).first()
            if run:
                run.revision_tool_calls = tool_calls
                run.draft_attempts = draft_attempts
                run.score_progression = _json.dumps(score_progression)
                if draft_iterations:
                    run.draft_iterations = _json.dumps(draft_iterations)
                session.commit()
        finally:
            session.close()
