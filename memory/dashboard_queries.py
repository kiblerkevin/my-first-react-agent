"""Mixin for dashboard query operations."""

import json as _json
from datetime import datetime, timedelta
from typing import Any

from memory.database import (
    ApiCallResult,
    Evaluation,
    PendingApproval,
    Summary,
    SummaryStats,
    WorkflowRun,
    get_session,
)
from utils.logger.logger import setup_logger

logger = setup_logger(__name__)


class DashboardMixin:
    """Dashboard query and reporting operations."""

    def get_recent_runs(self, limit: int = 30) -> list[dict[str, Any]]:
        """Get recent workflow runs."""
        session = get_session(self.engine)
        try:
            runs = (
                session.query(WorkflowRun)
                .order_by(WorkflowRun.id.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    'run_id': r.run_id,
                    'started_at': r.started_at.isoformat() if r.started_at else None,
                    'completed_at': r.completed_at.isoformat()
                    if r.completed_at
                    else None,
                    'duration_seconds': (r.completed_at - r.started_at).total_seconds()
                    if r.completed_at and r.started_at
                    else None,
                    'status': r.status,
                    'skip_reason': r.skip_reason,
                    'error': r.error,
                    'steps_completed': _json.loads(r.steps_completed)
                    if r.steps_completed
                    else [],
                    'scores_fetched': r.scores_fetched,
                    'articles_fetched': r.articles_fetched,
                    'articles_new': r.articles_new,
                    'summaries_count': r.summaries_count,
                    'overall_score': r.overall_score,
                    'email_sent': r.email_sent,
                    'revision_tool_calls': r.revision_tool_calls,
                    'draft_attempts': r.draft_attempts,
                    'score_progression': _json.loads(r.score_progression)
                    if r.score_progression
                    else [],
                    'publish_success': r.publish_success,
                }
                for r in runs
            ]
        finally:
            session.close()

    def get_evaluation_trends(self, days: int = 30) -> list[dict[str, Any]]:
        """Get evaluation trends over the last days."""
        session = get_session(self.engine)
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            evals = (
                session.query(Evaluation)
                .join(Summary)
                .filter(Summary.created_at >= cutoff)
                .order_by(Summary.created_at)
                .all()
            )

            by_date: dict[str, dict[str, float]] = {}
            for e in evals:
                date_key = (
                    e.summary.created_at.strftime('%Y-%m-%d')
                    if e.summary.created_at
                    else 'unknown'
                )
                if date_key not in by_date:
                    by_date[date_key] = {}
                by_date[date_key][e.criterion] = e.score

            return [{'date': d, **scores} for d, scores in sorted(by_date.items())]
        finally:
            session.close()

    def get_api_health(self, days: int = 30) -> list[dict[str, Any]]:
        """Get API health statistics over the last days."""
        session = get_session(self.engine)
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            results = (
                session.query(ApiCallResult)
                .filter(ApiCallResult.created_at >= cutoff)
                .all()
            )

            by_source: dict[str, dict[str, int]] = {}
            for r in results:
                if r.source_name not in by_source:
                    by_source[r.source_name] = {
                        'success': 0,
                        'error': 0,
                        'total_articles': 0,
                    }
                by_source[r.source_name][r.status] = (
                    by_source[r.source_name].get(r.status, 0) + 1
                )
                if r.article_count:
                    by_source[r.source_name]['total_articles'] += r.article_count

            return [{'source': s, **counts} for s, counts in by_source.items()]
        finally:
            session.close()

    def get_team_coverage(self, days: int = 30) -> dict[str, int]:
        """Get team coverage statistics over the last days."""
        session = get_session(self.engine)
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            summaries = (
                session.query(Summary).filter(Summary.created_at >= cutoff).all()
            )

            coverage: dict[str, int] = {}
            for s in summaries:
                teams = _json.loads(s.teams_covered) if s.teams_covered else []
                for team in teams:
                    coverage[team] = coverage.get(team, 0) + 1
            return coverage
        finally:
            session.close()

    def get_source_distribution(self, days: int = 30) -> dict[str, int]:
        """Get source distribution statistics over the last days."""
        session = get_session(self.engine)
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            results = (
                session.query(ApiCallResult)
                .filter(
                    ApiCallResult.created_at >= cutoff,
                    ApiCallResult.status == 'success',
                )
                .all()
            )

            dist: dict[str, int] = {}
            for r in results:
                if r.source_name not in ('espn',):
                    dist[r.source_name] = dist.get(r.source_name, 0) + (
                        r.article_count or 0
                    )
            return dist
        finally:
            session.close()

    def get_summary_cache_stats(self, days: int = 30) -> dict[str, Any]:
        """Get summary cache statistics over the last days."""
        session = get_session(self.engine)
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            stats = (
                session.query(SummaryStats)
                .join(WorkflowRun)
                .filter(WorkflowRun.started_at >= cutoff)
                .all()
            )

            totals: dict[str, int] = {'cache_hits': 0, 'cache_misses': 0}
            for s in stats:
                totals['cache_hits'] += s.cache_hits
                totals['cache_misses'] += s.cache_misses
            totals['total'] = totals['cache_hits'] + totals['cache_misses']
            totals['hit_rate'] = (
                round(totals['cache_hits'] / totals['total'] * 100, 1)
                if totals['total'] > 0
                else 0
            )
            return totals
        finally:
            session.close()

    def get_llm_stats(self, days: int = 30) -> dict[str, Any]:
        """Get LLM usage statistics over the last days."""
        session = get_session(self.engine)
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            runs = (
                session.query(WorkflowRun)
                .filter(WorkflowRun.started_at >= cutoff)
                .all()
            )

            totals: dict[str, Any] = {
                'total_input_tokens': 0,
                'total_output_tokens': 0,
                'estimated_cost': 0.0,
                'runs_tracked': 0,
                'usage_by_tool': {},
            }
            for r in runs:
                if r.total_input_tokens:
                    totals['total_input_tokens'] += r.total_input_tokens
                    totals['total_output_tokens'] += r.total_output_tokens or 0
                    totals['estimated_cost'] += r.estimated_cost or 0.0
                    totals['runs_tracked'] += 1
                if r.usage_by_tool:
                    for tool, usage in _json.loads(r.usage_by_tool).items():
                        if tool not in totals['usage_by_tool']:
                            totals['usage_by_tool'][tool] = {'input': 0, 'output': 0}
                        totals['usage_by_tool'][tool]['input'] += usage.get('input', 0)
                        totals['usage_by_tool'][tool]['output'] += usage.get(
                            'output', 0
                        )

            totals['estimated_cost'] = round(totals['estimated_cost'], 4)
            return totals
        finally:
            session.close()

    def get_run_iterations(self, run_id: str) -> dict[str, Any] | None:
        """Get the iterations for a workflow run."""
        session = get_session(self.engine)
        try:
            run = (
                session.query(
                    WorkflowRun.run_id,
                    WorkflowRun.started_at,
                    WorkflowRun.status,
                    WorkflowRun.overall_score,
                    WorkflowRun.draft_attempts,
                    WorkflowRun.score_progression,
                    WorkflowRun.draft_iterations,
                )
                .filter_by(run_id=run_id)
                .first()
            )

            if not run:
                return None

            drafts = _json.loads(run.draft_iterations) if run.draft_iterations else []

            summary = (
                session.query(Summary)
                .filter(Summary.created_at >= run.started_at)
                .order_by(Summary.created_at.desc())
                .first()
                if run.started_at
                else None
            )

            evaluations_by_id: dict[str, dict[str, Any]] = {}
            if summary:
                evals = session.query(Evaluation).filter_by(summary_id=summary.id).all()
                for e in evals:
                    if e.evaluation_id not in evaluations_by_id:
                        evaluations_by_id[e.evaluation_id] = {
                            'evaluation_id': e.evaluation_id,
                            'criteria_scores': {},
                            'criteria_reasoning': {},
                        }
                    evaluations_by_id[e.evaluation_id]['criteria_scores'][
                        e.criterion
                    ] = e.score
                    evaluations_by_id[e.evaluation_id]['criteria_reasoning'][
                        e.criterion
                    ] = e.reasoning or ''

            eval_list = list(evaluations_by_id.values())
            for ev in eval_list:
                scores = ev['criteria_scores']
                ev['overall_score'] = (
                    round(sum(scores.values()) / len(scores), 2) if scores else 0
                )

            iterations = []
            for i in range(max(len(drafts), len(eval_list))):
                iterations.append(
                    {
                        'attempt': i + 1,
                        'draft': drafts[i] if i < len(drafts) else None,
                        'evaluation': eval_list[i] if i < len(eval_list) else None,
                    }
                )

            return {
                'run_id': run.run_id,
                'started_at': run.started_at.isoformat() if run.started_at else None,
                'status': run.status,
                'overall_score': run.overall_score,
                'draft_attempts': run.draft_attempts,
                'score_progression': _json.loads(run.score_progression)
                if run.score_progression
                else [],
                'iterations': iterations,
            }
        finally:
            session.close()

    def get_runs_in_window(
        self, offset: int = 0, limit: int = 7
    ) -> list[dict[str, Any]]:
        """Get workflow runs in a window."""
        session = get_session(self.engine)
        try:
            runs = (
                session.query(
                    WorkflowRun.run_id,
                    WorkflowRun.started_at,
                    WorkflowRun.status,
                    WorkflowRun.overall_score,
                    WorkflowRun.draft_attempts,
                )
                .filter(WorkflowRun.status.in_(['success', 'failed']))
                .order_by(WorkflowRun.started_at.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )

            return [
                {
                    'run_id': r.run_id,
                    'started_at': r.started_at.isoformat() if r.started_at else None,
                    'status': r.status,
                    'overall_score': r.overall_score,
                    'draft_attempts': r.draft_attempts,
                }
                for r in runs
            ]
        finally:
            session.close()

    def get_runs_in_range(
        self, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        """Get workflow runs in a date range."""
        session = get_session(self.engine)
        try:
            start = datetime.fromisoformat(start_date)
            end = datetime.fromisoformat(end_date)

            runs = (
                session.query(
                    WorkflowRun.run_id,
                    WorkflowRun.started_at,
                    WorkflowRun.status,
                    WorkflowRun.overall_score,
                    WorkflowRun.draft_attempts,
                )
                .filter(
                    WorkflowRun.started_at >= start,
                    WorkflowRun.started_at <= end,
                    WorkflowRun.status.in_(['success', 'failed']),
                )
                .order_by(WorkflowRun.started_at.desc())
                .all()
            )

            return [
                {
                    'run_id': r.run_id,
                    'started_at': r.started_at.isoformat() if r.started_at else None,
                    'status': r.status,
                    'overall_score': r.overall_score,
                    'draft_attempts': r.draft_attempts,
                }
                for r in runs
            ]
        finally:
            session.close()

    def get_total_run_count(self) -> int:
        """Get the total count of workflow runs."""
        session = get_session(self.engine)
        try:
            return (
                session.query(WorkflowRun)
                .filter(WorkflowRun.status.in_(['success', 'failed']))
                .count()
            )
        finally:
            session.close()
