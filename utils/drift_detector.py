"""Drift detection for monitoring agent output quality over time."""

from typing import Any

import yaml

from memory.memory import Memory
from utils.logger.logger import setup_logger

logger = setup_logger(__name__)

DRIFT_CONFIG_PATH = 'config/drift.yaml'


class DriftDetector:
    """Evaluates workflow metrics against configurable thresholds."""

    def __init__(self, memory: Memory | None = None) -> None:
        """Initialize with drift config and memory layer.

        Args:
            memory: Memory instance. Creates one if not provided.
        """
        with open(DRIFT_CONFIG_PATH, 'r') as f:
            self.config: dict[str, Any] = yaml.safe_load(f)
        self.metrics_config: dict[str, Any] = self.config['metrics']
        self.memory = memory or Memory()

    def check(self, run_id: str | None = None) -> dict[str, Any]:
        """Run all drift checks and return new alerts and recoveries.

        Args:
            run_id: The workflow run that triggered this check.

        Returns:
            Dict with 'new_alerts' and 'recoveries' lists.
        """
        max_window = max(
            m.get('window', 5) for m in self.metrics_config.values()
        )
        data = self.memory.get_drift_metrics(window=max_window)

        results: dict[str, Any] = {'new_alerts': [], 'recoveries': []}

        evaluations = self._evaluate_all(data)

        for metric_name, evaluation in evaluations.items():
            is_breaching = evaluation['breaching']
            has_alert = self.memory.has_active_alert(metric_name)

            if is_breaching and not has_alert:
                # New breach — create alert
                config = self.metrics_config[metric_name]
                self.memory.create_drift_alert(
                    metric_name=metric_name,
                    metric_value=evaluation['value'],
                    threshold=config['threshold'],
                    run_id=run_id,
                )
                results['new_alerts'].append({
                    'metric_name': metric_name,
                    'value': evaluation['value'],
                    'threshold': config['threshold'],
                    'description': config['description'],
                    'suggested_actions': config['suggested_actions'],
                })
                logger.warning(
                    f"Drift detected: {metric_name} = {evaluation['value']} "
                    f"(threshold: {config['threshold']})"
                )

            elif not is_breaching and has_alert:
                # Recovery — resolve alert
                self.memory.resolve_drift_alert(metric_name)
                results['recoveries'].append({
                    'metric_name': metric_name,
                    'value': evaluation['value'],
                    'description': self.metrics_config[metric_name]['description'],
                })
                logger.info(
                    f"Drift recovered: {metric_name} = {evaluation['value']}"
                )

        return results

    def _evaluate_all(self, data: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """Evaluate all metrics against their thresholds.

        Args:
            data: Raw metrics data from memory.get_drift_metrics().

        Returns:
            Dict mapping metric_name to {breaching: bool, value: float}.
        """
        runs = data['runs']
        approvals = data['approvals']

        return {
            'average_overall_score': self._eval_average_overall_score(runs),
            'consecutive_failures': self._eval_consecutive_failures(runs),
            'average_revision_tool_calls': self._eval_average_revision_tool_calls(runs),
            'consecutive_low_completeness': self._eval_consecutive_low_criterion(runs, 'completeness'),
            'consecutive_low_accuracy': self._eval_consecutive_low_criterion(runs, 'accuracy'),
            'approval_rejection_rate': self._eval_approval_rejection_rate(approvals),
            'consecutive_no_news_skips': self._eval_consecutive_no_news_skips(runs),
        }

    def _eval_average_overall_score(self, runs: list[dict]) -> dict[str, Any]:
        """Evaluate average overall score across recent successful runs."""
        config = self.metrics_config['average_overall_score']
        window = config['window']
        scores = [
            r['overall_score']
            for r in runs[:window]
            if r.get('overall_score') is not None
        ]
        if not scores:
            return {'breaching': False, 'value': 0.0}
        avg = sum(scores) / len(scores)
        return {
            'breaching': avg < config['threshold'],
            'value': round(avg, 2),
        }

    def _eval_consecutive_failures(self, runs: list[dict]) -> dict[str, Any]:
        """Count consecutive failures from most recent run."""
        config = self.metrics_config['consecutive_failures']
        count = 0
        for r in runs:
            if r['status'] == 'failed':
                count += 1
            else:
                break
        return {
            'breaching': count >= config['threshold'],
            'value': count,
        }

    def _eval_average_revision_tool_calls(self, runs: list[dict]) -> dict[str, Any]:
        """Evaluate average revision tool calls across recent successful runs."""
        config = self.metrics_config['average_revision_tool_calls']
        window = config['window']
        calls = [
            r['revision_tool_calls']
            for r in runs[:window]
            if r.get('revision_tool_calls') is not None
        ]
        if not calls:
            return {'breaching': False, 'value': 0.0}
        avg = sum(calls) / len(calls)
        return {
            'breaching': avg > config['threshold'],
            'value': round(avg, 2),
        }

    def _eval_consecutive_low_criterion(
        self, runs: list[dict], criterion: str
    ) -> dict[str, Any]:
        """Evaluate consecutive runs with a criterion below threshold.

        Uses overall_score as proxy since per-criterion scores aren't in WorkflowRun.
        """
        metric_key = f'consecutive_low_{criterion}'
        config = self.metrics_config[metric_key]
        window = config['window']

        scores = [
            r['overall_score']
            for r in runs[:window]
            if r.get('overall_score') is not None
        ]
        if len(scores) < window:
            return {'breaching': False, 'value': 0.0}

        all_below = all(s < config['threshold'] for s in scores)
        return {
            'breaching': all_below,
            'value': round(min(scores), 2) if scores else 0.0,
        }

    def _eval_approval_rejection_rate(self, approvals: list[dict]) -> dict[str, Any]:
        """Evaluate rejection rate across recent approvals."""
        config = self.metrics_config['approval_rejection_rate']
        window = config['window']
        recent = approvals[:window]
        if not recent:
            return {'breaching': False, 'value': 0.0}
        rejections = sum(1 for a in recent if a['status'] == 'rejected')
        rate = (rejections / len(recent)) * 100
        return {
            'breaching': rate > config['threshold'],
            'value': round(rate, 1),
        }

    def _eval_consecutive_no_news_skips(self, runs: list[dict]) -> dict[str, Any]:
        """Count consecutive no-news skips from most recent run."""
        config = self.metrics_config['consecutive_no_news_skips']
        count = 0
        for r in runs:
            if r['status'] == 'skipped' and r.get('skip_reason') and 'No new articles' in r['skip_reason']:
                count += 1
            else:
                break
        return {
            'breaching': count >= config['threshold'],
            'value': count,
        }
