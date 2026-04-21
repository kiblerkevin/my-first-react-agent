"""Tests for tools/fetch_scores_tool.py."""

from unittest.mock import MagicMock, patch

from models.inputs.fetch_scores_input import FetchScoresInput
from tools.fetch_scores_tool import FetchScoresTool


class TestFetchScoresTool:
    """Tests for FetchScoresTool.execute."""

    @patch('tools.fetch_scores_tool.Memory')
    @patch('tools.fetch_scores_tool.ESPNCollector')
    def test_returns_scores_on_success(
        self, mock_collector_cls, mock_memory_cls, mock_scores
    ):
        mock_collector = MagicMock()
        mock_collector.collect_articles.return_value = mock_scores
        mock_collector_cls.return_value = mock_collector
        mock_memory_cls.return_value = MagicMock()

        tool = FetchScoresTool()
        result = tool.execute(FetchScoresInput())

        assert result.score_count == 3
        assert result.scores == mock_scores
        assert result.errors == []

    @patch('tools.fetch_scores_tool.Memory')
    @patch('tools.fetch_scores_tool.ESPNCollector')
    def test_captures_error_on_failure(self, mock_collector_cls, mock_memory_cls):
        mock_collector = MagicMock()
        mock_collector.collect_articles.side_effect = Exception('API down')
        mock_collector_cls.return_value = mock_collector
        mock_memory_cls.return_value = MagicMock()

        tool = FetchScoresTool()
        result = tool.execute(FetchScoresInput())

        assert result.score_count == 0
        assert len(result.errors) == 1
        assert 'API down' in result.errors[0]

    @patch('tools.fetch_scores_tool.Memory')
    @patch('tools.fetch_scores_tool.ESPNCollector')
    def test_persists_api_call_result_with_run_id(
        self, mock_collector_cls, mock_memory_cls, mock_scores
    ):
        mock_collector = MagicMock()
        mock_collector.collect_articles.return_value = mock_scores
        mock_collector_cls.return_value = mock_collector
        mock_memory = MagicMock()
        mock_memory.get_workflow_run_db_id.return_value = 42
        mock_memory_cls.return_value = mock_memory

        tool = FetchScoresTool()
        tool.execute(FetchScoresInput(run_id='test-run-123'))

        mock_memory.save_api_call_result.assert_called_once_with(
            42, 'espn', 'success', 3
        )


class TestFetchScoresToolEdgeCases:
    """Tests for FetchScoresTool error persistence."""

    @patch('tools.fetch_scores_tool.Memory')
    @patch('tools.fetch_scores_tool.ESPNCollector')
    def test_persists_error_with_run_id(self, mock_collector_cls, mock_memory_cls):
        mock_collector = MagicMock()
        mock_collector.collect_articles.side_effect = Exception('ESPN down')
        mock_collector_cls.return_value = mock_collector
        mock_memory = MagicMock()
        mock_memory.get_workflow_run_db_id.return_value = 5
        mock_memory_cls.return_value = mock_memory

        tool = FetchScoresTool()
        tool.execute(FetchScoresInput(run_id='run-err'))

        mock_memory.save_api_call_result.assert_called_once_with(
            5, 'espn', 'error', error='ESPN down'
        )
