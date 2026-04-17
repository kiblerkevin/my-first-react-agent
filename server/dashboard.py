import os
import sys

from flask import Blueprint, jsonify, render_template

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.memory import Memory

dashboard_bp = Blueprint('dashboard', __name__, template_folder='templates')
memory = Memory()


@dashboard_bp.route('/dashboard')
def index():
    return render_template('dashboard.html')


@dashboard_bp.route('/dashboard/api/runs')
def api_runs():
    return jsonify(memory.get_recent_runs(30))


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
