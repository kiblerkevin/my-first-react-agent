import os
import sys

from flask import Blueprint, jsonify, render_template, request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.memory import Memory

dashboard_bp = Blueprint('dashboard', __name__, template_folder='templates')
memory = Memory()


@dashboard_bp.route('/dashboard')
def index():
    return render_template('dashboard.html')


@dashboard_bp.route('/dashboard/iterations')
def iterations():
    return render_template('iterations.html')


@dashboard_bp.route('/dashboard/api/runs')
def api_runs():
    return jsonify(memory.get_recent_runs(30))


@dashboard_bp.route('/dashboard/api/runs/window')
def api_runs_window():
    offset = request.args.get('offset', 0, type=int)
    limit = request.args.get('limit', 7, type=int)
    total = memory.get_total_run_count()
    runs = memory.get_runs_in_window(offset, limit)
    return jsonify({'runs': runs, 'total': total, 'offset': offset, 'limit': limit})


@dashboard_bp.route('/dashboard/api/runs/range')
def api_runs_range():
    start = request.args.get('start', '')
    end = request.args.get('end', '')
    if not start or not end:
        return jsonify({'error': 'start and end parameters required'}), 400
    runs = memory.get_runs_in_range(start, end)
    return jsonify({'runs': runs})


@dashboard_bp.route('/dashboard/api/iterations/<run_id>')
def api_iterations(run_id):
    data = memory.get_run_iterations(run_id)
    if not data:
        return jsonify({'error': 'Run not found'}), 404
    return jsonify(data)


@dashboard_bp.route('/dashboard/api/evaluations')
def api_evaluations():
    return jsonify(memory.get_evaluation_trends(30))


@dashboard_bp.route('/dashboard/api/health')
def api_health():
    return jsonify(memory.get_api_health(30))


@dashboard_bp.route('/dashboard/api/approvals')
def api_approvals():
    return jsonify(memory.get_approval_stats(30))


@dashboard_bp.route('/dashboard/api/teams')
def api_teams():
    return jsonify(memory.get_team_coverage(30))


@dashboard_bp.route('/dashboard/api/sources')
def api_sources():
    return jsonify(memory.get_source_distribution(30))


@dashboard_bp.route('/dashboard/api/cache')
def api_cache():
    return jsonify(memory.get_summary_cache_stats(30))
