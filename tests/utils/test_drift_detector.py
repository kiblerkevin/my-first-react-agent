"""Tests for utils/drift_detector.py."""

from unittest.mock import MagicMock, patch

from utils.drift_detector import DriftDetector


def _make_detector(memory=None):
    """Create a DriftDetector with mocked config and optional memory."""
    config = {
        'metrics': {
            'average_overall_score': {
                'threshold': 7.0,
                'comparison': 'below',
                'window': 5,
                'description': 'Avg score',
                'suggested_actions': ['Fix prompts'],
            },
            'consecutive_failures': {
                'threshold': 3,
                'comparison': 'at_or_above',
                'window': 10,
                'description': 'Failures',
                'suggested_actions': ['Check APIs'],
            },
            'average_revision_tool_calls': {
                'threshold': 5,
                'comparison': 'above',
                'window': 5,
                'description': 'Avg tool calls',
                'suggested_actions': ['Lower floors'],
            },
            'consecutive_low_completeness': {
                'threshold': 6.0,
                'comparison': 'below',
                'window': 3,
                'description': 'Low completeness',
                'suggested_actions': ['Check ESPN'],
            },
            'consecutive_low_accuracy': {
                'threshold': 7.0,
                'comparison': 'below',
                'window': 2,
                'description': 'Low accuracy',
                'suggested_actions': ['Verify scores'],
            },
            'approval_rejection_rate': {
                'threshold': 50,
                'comparison': 'above',
                'window': 7,
                'description': 'Rejection rate',
                'suggested_actions': ['Review feedback'],
            },
            'consecutive_no_news_skips': {
                'threshold': 3,
                'comparison': 'at_or_above',
                'window': 10,
                'description': 'No-news skips',
                'suggested_actions': ['Check APIs'],
            },
        }
    }
    with (
        patch('utils.drift_detector.yaml.safe_load', return_value=config),
        patch('builtins.open'),
    ):
        detector = DriftDetector(memory=memory or MagicMock())
    return detector


class TestDriftDetectorEvaluation:
    """Tests for individual metric evaluation methods."""

    def test_average_overall_score_healthy(self):
        detector = _make_detector()
        runs = [{'overall_score': 8.0, 'status': 'success'} for _ in range(5)]
        result = detector._eval_average_overall_score(runs)
        assert result['breaching'] is False
        assert result['value'] == 8.0

    def test_average_overall_score_breaching(self):
        detector = _make_detector()
        runs = [{'overall_score': 6.0, 'status': 'success'} for _ in range(5)]
        result = detector._eval_average_overall_score(runs)
        assert result['breaching'] is True
        assert result['value'] == 6.0

    def test_average_overall_score_no_data(self):
        detector = _make_detector()
        runs = [{'overall_score': None, 'status': 'skipped'} for _ in range(5)]
        result = detector._eval_average_overall_score(runs)
        assert result['breaching'] is False

    def test_consecutive_failures_healthy(self):
        detector = _make_detector()
        runs = [{'status': 'success'}, {'status': 'failed'}, {'status': 'success'}]
        result = detector._eval_consecutive_failures(runs)
        assert result['breaching'] is False
        assert result['value'] == 0

    def test_consecutive_failures_breaching(self):
        detector = _make_detector()
        runs = [
            {'status': 'failed'},
            {'status': 'failed'},
            {'status': 'failed'},
            {'status': 'success'},
        ]
        result = detector._eval_consecutive_failures(runs)
        assert result['breaching'] is True
        assert result['value'] == 3

    def test_average_revision_tool_calls_healthy(self):
        detector = _make_detector()
        runs = [{'revision_tool_calls': 4} for _ in range(5)]
        result = detector._eval_average_revision_tool_calls(runs)
        assert result['breaching'] is False

    def test_average_revision_tool_calls_breaching(self):
        detector = _make_detector()
        runs = [{'revision_tool_calls': 6} for _ in range(5)]
        result = detector._eval_average_revision_tool_calls(runs)
        assert result['breaching'] is True

    def test_average_revision_tool_calls_no_data(self):
        detector = _make_detector()
        runs = [{'revision_tool_calls': None} for _ in range(5)]
        result = detector._eval_average_revision_tool_calls(runs)
        assert result['breaching'] is False

    def test_consecutive_low_completeness_healthy(self):
        detector = _make_detector()
        runs = [{'overall_score': 8.0}, {'overall_score': 7.0}, {'overall_score': 9.0}]
        result = detector._eval_consecutive_low_criterion(runs, 'completeness')
        assert result['breaching'] is False

    def test_consecutive_low_completeness_breaching(self):
        detector = _make_detector()
        runs = [{'overall_score': 5.0}, {'overall_score': 4.0}, {'overall_score': 5.5}]
        result = detector._eval_consecutive_low_criterion(runs, 'completeness')
        assert result['breaching'] is True

    def test_consecutive_low_completeness_insufficient_data(self):
        detector = _make_detector()
        runs = [{'overall_score': 5.0}]  # less than window of 3
        result = detector._eval_consecutive_low_criterion(runs, 'completeness')
        assert result['breaching'] is False

    def test_consecutive_low_accuracy_breaching(self):
        detector = _make_detector()
        runs = [{'overall_score': 6.0}, {'overall_score': 5.0}]
        result = detector._eval_consecutive_low_criterion(runs, 'accuracy')
        assert result['breaching'] is True

    def test_approval_rejection_rate_healthy(self):
        detector = _make_detector()
        approvals = [{'status': 'approved'} for _ in range(7)]
        result = detector._eval_approval_rejection_rate(approvals)
        assert result['breaching'] is False
        assert result['value'] == 0.0

    def test_approval_rejection_rate_breaching(self):
        detector = _make_detector()
        approvals = [{'status': 'rejected'}] * 5 + [{'status': 'approved'}] * 2
        result = detector._eval_approval_rejection_rate(approvals)
        assert result['breaching'] is True
        assert result['value'] > 50

    def test_approval_rejection_rate_no_data(self):
        detector = _make_detector()
        result = detector._eval_approval_rejection_rate([])
        assert result['breaching'] is False

    def test_consecutive_no_news_skips_healthy(self):
        detector = _make_detector()
        runs = [
            {'status': 'success', 'skip_reason': None},
            {'status': 'skipped', 'skip_reason': 'No new articles found.'},
        ]
        result = detector._eval_consecutive_no_news_skips(runs)
        assert result['breaching'] is False
        assert result['value'] == 0

    def test_consecutive_no_news_skips_breaching(self):
        detector = _make_detector()
        runs = [
            {'status': 'skipped', 'skip_reason': 'No new articles found.'},
            {'status': 'skipped', 'skip_reason': 'No new articles found.'},
            {'status': 'skipped', 'skip_reason': 'No new articles found.'},
            {'status': 'success', 'skip_reason': None},
        ]
        result = detector._eval_consecutive_no_news_skips(runs)
        assert result['breaching'] is True
        assert result['value'] == 3


class TestDriftDetectorCheck:
    """Tests for the full check() method with alert creation and recovery."""

    def test_creates_alert_on_new_breach(self):
        memory = MagicMock()
        memory.get_drift_metrics.return_value = {
            'runs': [
                {
                    'status': 'failed',
                    'overall_score': None,
                    'revision_tool_calls': None,
                    'skip_reason': None,
                }
            ]
            * 5,
            'approvals': [],
        }
        memory.has_active_alert.return_value = False

        detector = _make_detector(memory=memory)
        results = detector.check(run_id='test-run')

        assert len(results['new_alerts']) > 0
        memory.create_drift_alert.assert_called()

    def test_suppresses_duplicate_alert(self):
        memory = MagicMock()
        memory.get_drift_metrics.return_value = {
            'runs': [
                {
                    'status': 'failed',
                    'overall_score': None,
                    'revision_tool_calls': None,
                    'skip_reason': None,
                }
            ]
            * 5,
            'approvals': [],
        }
        memory.has_active_alert.return_value = True  # already alerted

        detector = _make_detector(memory=memory)
        results = detector.check(run_id='test-run')

        assert len(results['new_alerts']) == 0
        memory.create_drift_alert.assert_not_called()

    def test_resolves_alert_on_recovery(self):
        memory = MagicMock()
        memory.get_drift_metrics.return_value = {
            'runs': [
                {
                    'status': 'success',
                    'overall_score': 9.0,
                    'revision_tool_calls': 3,
                    'skip_reason': None,
                }
            ]
            * 5,
            'approvals': [{'status': 'approved'}] * 7,
        }
        # All metrics healthy, but has active alerts
        memory.has_active_alert.return_value = True

        detector = _make_detector(memory=memory)
        results = detector.check(run_id='test-run')

        assert len(results['recoveries']) > 0
        memory.resolve_drift_alert.assert_called()

    def test_no_alerts_when_all_healthy(self):
        memory = MagicMock()
        memory.get_drift_metrics.return_value = {
            'runs': [
                {
                    'status': 'success',
                    'overall_score': 9.0,
                    'revision_tool_calls': 3,
                    'skip_reason': None,
                }
            ]
            * 5,
            'approvals': [{'status': 'approved'}] * 7,
        }
        memory.has_active_alert.return_value = False

        detector = _make_detector(memory=memory)
        results = detector.check(run_id='test-run')

        assert results['new_alerts'] == []
        assert results['recoveries'] == []
