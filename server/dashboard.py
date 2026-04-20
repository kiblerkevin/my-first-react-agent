"""Flask blueprint for the admin dashboard with JSON API endpoints."""

import os
import sys

from flask import Blueprint, Response, jsonify, render_template, request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.memory import Memory

dashboard_bp = Blueprint('dashboard', __name__, template_folder='templates')
memory = Memory()


@dashboard_bp.route('/dashboard')
def index() -> str:
    """Render the main dashboard page."""
    return render_template('dashboard.html')


@dashboard_bp.route('/dashboard/iterations')
def iterations() -> str:
    """Render the iterations detail page."""
    return render_template('iterations.html')


@dashboard_bp.route('/dashboard/api/runs')
def api_runs() -> Response:
    """Return the 30 most recent workflow runs as JSON."""
    return jsonify(memory.get_recent_runs(30))


@dashboard_bp.route('/dashboard/api/runs/window')
def api_runs_window() -> Response:
    """Return a paginated window of workflow runs as JSON."""
    offset = request.args.get('offset', 0, type=int)
    limit = request.args.get('limit', 7, type=int)
    total = memory.get_total_run_count()
    runs = memory.get_runs_in_window(offset, limit)
    return jsonify(
        {
            'runs': runs,
            'total': total,
            'offset': offset,
            'limit': limit,
        }
    )


@dashboard_bp.route('/dashboard/api/runs/range')
def api_runs_range() -> Response:
    """Return workflow runs within a date range as JSON."""
    start = request.args.get('start', '')
    end = request.args.get('end', '')
    if not start or not end:
        return jsonify({'error': 'start and end parameters required'}), 400  # type: ignore[return-value]
    runs = memory.get_runs_in_range(start, end)
    return jsonify({'runs': runs})


@dashboard_bp.route('/dashboard/api/iterations/<run_id>')
def api_iterations(run_id: str) -> Response:
    """Return draft iterations for a specific run as JSON."""
    data = memory.get_run_iterations(run_id)
    if not data:
        return jsonify({'error': 'Run not found'}), 404  # type: ignore[return-value]
    return jsonify(data)


@dashboard_bp.route('/dashboard/api/evaluations')
def api_evaluations() -> Response:
    """Return evaluation score trends over the last 30 days."""
    return jsonify(memory.get_evaluation_trends(30))


@dashboard_bp.route('/dashboard/api/health')
def api_health() -> Response:
    """Return API health statistics over the last 30 days."""
    return jsonify(memory.get_api_health(30))


@dashboard_bp.route('/dashboard/api/approvals')
def api_approvals() -> Response:
    """Return approval statistics over the last 30 days."""
    return jsonify(memory.get_approval_stats(30))


@dashboard_bp.route('/dashboard/api/teams')
def api_teams() -> Response:
    """Return team coverage statistics over the last 30 days."""
    return jsonify(memory.get_team_coverage(30))


@dashboard_bp.route('/dashboard/api/sources')
def api_sources() -> Response:
    """Return source distribution statistics over the last 30 days."""
    return jsonify(memory.get_source_distribution(30))


@dashboard_bp.route('/dashboard/api/cache')
def api_cache() -> Response:
    """Return summary cache hit/miss statistics over the last 30 days."""
    return jsonify(memory.get_summary_cache_stats(30))


@dashboard_bp.route('/dashboard/api/drift')
def api_drift() -> Response:
    """Return active drift alerts with full details."""
    alerts = memory.get_active_drift_alerts()
    return jsonify({'active_alerts': alerts, 'count': len(alerts)})
