"""Tests for tools/summarize_article_tool.py."""

import json
from unittest.mock import MagicMock, patch

from models.inputs.summarize_article_input import SummarizeArticleInput
from tools.summarize_article_tool import SummarizeArticleTool


class TestSummarizeArticleTool:
    """Tests for SummarizeArticleTool.execute."""

    @patch('tools.summarize_article_tool.Memory')
    @patch('tools.summarize_article_tool.ClaudeClient')
    @patch('tools.summarize_article_tool.yaml.safe_load')
    @patch('builtins.open')
    def test_returns_cached_summary(
        self, mock_open, mock_yaml, mock_claude_cls, mock_memory_cls
    ):
        mock_yaml.return_value = {
            'claude_summarizer': {'model': 'x', 'temperature': 0.1, 'max_tokens': 512}
        }
        cached = {
            'url': 'http://x.com',
            'team': 'Cubs',
            'summary': 'Cached.',
            'event_type': 'game_recap',
            'players_mentioned': [],
            'is_relevant': True,
        }
        mock_memory = MagicMock()
        mock_memory.get_article_summary.return_value = cached
        mock_memory_cls.return_value = mock_memory

        tool = SummarizeArticleTool()
        result = tool.execute(
            SummarizeArticleInput(url='http://x.com', title='Test', team='Cubs')
        )

        assert result.summary == 'Cached.'
        assert tool.last_cache_hit is True
        mock_claude_cls.return_value.send_message.assert_not_called()

    @patch('tools.summarize_article_tool.rate_limited_request')
    @patch('tools.summarize_article_tool.Memory')
    @patch('tools.summarize_article_tool.ClaudeClient')
    @patch('tools.summarize_article_tool.yaml.safe_load')
    @patch('builtins.open')
    def test_calls_claude_on_cache_miss(
        self, mock_open, mock_yaml, mock_claude_cls, mock_memory_cls, mock_request
    ):
        mock_yaml.return_value = {
            'claude_summarizer': {'model': 'x', 'temperature': 0.1, 'max_tokens': 512}
        }
        mock_memory = MagicMock()
        mock_memory.get_article_summary.return_value = None
        mock_memory_cls.return_value = mock_memory

        mock_response = MagicMock(
            status_code=200,
            text='<html><body><p>Article content here</p></body></html>',
        )
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        claude_response = json.dumps(
            {
                'summary': 'New summary.',
                'event_type': 'game_recap',
                'players_mentioned': ['A'],
                'is_relevant': True,
            }
        )
        mock_claude = MagicMock()
        mock_claude.send_message.return_value = claude_response
        mock_claude_cls.return_value = mock_claude

        tool = SummarizeArticleTool()
        tool.claude_client = mock_claude
        result = tool.execute(
            SummarizeArticleInput(url='http://x.com', title='Test', team='Cubs')
        )

        assert result.summary == 'New summary.'
        assert tool.last_cache_hit is False
        mock_memory.save_article_summary.assert_called_once()

    @patch('tools.summarize_article_tool.rate_limited_request')
    @patch('tools.summarize_article_tool.Memory')
    @patch('tools.summarize_article_tool.ClaudeClient')
    @patch('tools.summarize_article_tool.yaml.safe_load')
    @patch('builtins.open')
    def test_marks_irrelevant_when_content_unavailable(
        self, mock_open, mock_yaml, mock_claude_cls, mock_memory_cls, mock_request
    ):
        mock_yaml.return_value = {
            'claude_summarizer': {'model': 'x', 'temperature': 0.1, 'max_tokens': 512}
        }
        mock_memory = MagicMock()
        mock_memory.get_article_summary.return_value = None
        mock_memory_cls.return_value = mock_memory

        mock_request.side_effect = Exception('Timeout')

        claude_response = json.dumps(
            {
                'summary': 'Title only.',
                'event_type': 'other',
                'players_mentioned': [],
                'is_relevant': True,
            }
        )
        mock_claude = MagicMock()
        mock_claude.send_message.return_value = claude_response
        mock_claude_cls.return_value = mock_claude

        tool = SummarizeArticleTool()
        tool.claude_client = mock_claude
        result = tool.execute(
            SummarizeArticleInput(url='http://x.com', title='Test', team='Cubs')
        )

        assert result.is_relevant is False  # forced False when content unavailable


class TestSummarizeArticleToolEdgeCases:
    """Tests for error handling in SummarizeArticleTool."""

    @patch('tools.summarize_article_tool.rate_limited_request')
    @patch('tools.summarize_article_tool.Memory')
    @patch('tools.summarize_article_tool.ClaudeClient')
    @patch('tools.summarize_article_tool.yaml.safe_load')
    @patch('builtins.open')
    def test_returns_fallback_on_claude_error(
        self, mock_open, mock_yaml, mock_claude_cls, mock_memory_cls, mock_request
    ):
        mock_yaml.return_value = {
            'claude_summarizer': {'model': 'x', 'temperature': 0.1, 'max_tokens': 512}
        }
        mock_memory = MagicMock()
        mock_memory.get_article_summary.return_value = None
        mock_memory_cls.return_value = mock_memory

        # Content fetch succeeds
        mock_response = MagicMock(
            status_code=200, text='<html><body><p>Text</p></body></html>'
        )
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        # Claude raises
        mock_claude = MagicMock()
        mock_claude.send_message.side_effect = Exception('Claude down')
        mock_claude_cls.return_value = mock_claude

        tool = SummarizeArticleTool()
        tool.claude_client = mock_claude
        result = tool.execute(
            SummarizeArticleInput(
                url='http://x.com', title='Fallback Title', team='Cubs'
            )
        )

        assert result.summary == 'Fallback Title'
        assert result.is_relevant is False
        assert result.event_type == 'other'

    @patch('tools.summarize_article_tool.rate_limited_request')
    @patch('tools.summarize_article_tool.Memory')
    @patch('tools.summarize_article_tool.ClaudeClient')
    @patch('tools.summarize_article_tool.yaml.safe_load')
    @patch('builtins.open')
    def test_decomposes_html_tags(
        self, mock_open, mock_yaml, mock_claude_cls, mock_memory_cls, mock_request
    ):
        """Line 161: verifies script/style/nav tags are removed."""
        mock_yaml.return_value = {
            'claude_summarizer': {'model': 'x', 'temperature': 0.1, 'max_tokens': 512}
        }
        mock_memory = MagicMock()
        mock_memory.get_article_summary.return_value = None
        mock_memory_cls.return_value = mock_memory

        html = '<html><body><script>evil()</script><nav>Nav</nav><p>Real content</p></body></html>'
        mock_response = MagicMock(status_code=200, text=html)
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        claude_response = json.dumps(
            {
                'summary': 'S',
                'event_type': 'other',
                'players_mentioned': [],
                'is_relevant': True,
            }
        )
        mock_claude = MagicMock()
        mock_claude.send_message.return_value = claude_response
        mock_claude_cls.return_value = mock_claude

        tool = SummarizeArticleTool()
        tool.claude_client = mock_claude
        tool.execute(SummarizeArticleInput(url='http://x.com', title='T', team='Cubs'))

        # Verify the prompt sent to Claude doesn't contain script/nav content
        prompt = mock_claude.send_message.call_args[0][0]
        assert 'evil()' not in prompt
        assert 'Nav' not in prompt
        assert 'Real content' in prompt
