"""Tests for tools/create_blog_draft_tool.py."""

import json
from unittest.mock import MagicMock, patch

from models.inputs.create_blog_draft_input import CreateBlogDraftInput
from tools.create_blog_draft_tool import CreateBlogDraftTool


class TestCreateBlogDraftTool:
    """Tests for CreateBlogDraftTool.execute."""

    @patch('tools.create_blog_draft_tool.ClaudeClient')
    @patch('tools.create_blog_draft_tool.yaml.safe_load')
    @patch('builtins.open')
    def test_creates_initial_draft(
        self,
        mock_open,
        mock_yaml,
        mock_claude_cls,
        mock_scores,
        mock_summaries,
        mock_draft,
    ):
        mock_yaml.return_value = {
            'claude_drafter': {'model': 'x', 'temperature': 0.5, 'max_tokens': 4096}
        }
        mock_claude = MagicMock()
        mock_claude.send_message.return_value = json.dumps(mock_draft)
        mock_claude_cls.return_value = mock_claude

        tool = CreateBlogDraftTool()
        tool.claude_client = mock_claude
        result = tool.execute(
            CreateBlogDraftInput(summaries=mock_summaries, scores=mock_scores)
        )

        assert result.title == mock_draft['title']
        assert 'Chicago Cubs' in result.teams_covered
        assert result.article_count == len(mock_summaries)

    @patch('tools.create_blog_draft_tool.ClaudeClient')
    @patch('tools.create_blog_draft_tool.yaml.safe_load')
    @patch('builtins.open')
    def test_revision_mode_uses_revision_prompt(
        self,
        mock_open,
        mock_yaml,
        mock_claude_cls,
        mock_scores,
        mock_summaries,
        mock_draft,
    ):
        mock_yaml.return_value = {
            'claude_drafter': {'model': 'x', 'temperature': 0.5, 'max_tokens': 4096}
        }
        mock_claude = MagicMock()
        mock_claude.send_message.return_value = json.dumps(mock_draft)
        mock_claude_cls.return_value = mock_claude

        tool = CreateBlogDraftTool()
        tool.claude_client = mock_claude
        tool.execute(
            CreateBlogDraftInput(
                summaries=mock_summaries,
                scores=mock_scores,
                current_draft='<h1>Old draft</h1>',
                revision_notes={'seo': ['Shorten title']},
            )
        )

        # Verify the prompt sent to Claude contains revision context
        call_args = mock_claude.send_message.call_args[0][0]
        assert 'CURRENT DRAFT' in call_args
        assert 'REVISION NOTES' in call_args

    @patch('tools.create_blog_draft_tool.ClaudeClient')
    @patch('tools.create_blog_draft_tool.yaml.safe_load')
    @patch('builtins.open')
    def test_returns_empty_on_error(
        self, mock_open, mock_yaml, mock_claude_cls, mock_scores, mock_summaries
    ):
        mock_yaml.return_value = {
            'claude_drafter': {'model': 'x', 'temperature': 0.5, 'max_tokens': 4096}
        }
        mock_claude = MagicMock()
        mock_claude.send_message.side_effect = Exception('LLM error')
        mock_claude_cls.return_value = mock_claude

        tool = CreateBlogDraftTool()
        tool.claude_client = mock_claude
        result = tool.execute(
            CreateBlogDraftInput(summaries=mock_summaries, scores=mock_scores)
        )

        assert result.title == ''
        assert result.content == ''


class TestCreateBlogDraftToolEdgeCases:
    """Tests for edge cases in CreateBlogDraftTool."""

    @patch('tools.create_blog_draft_tool.ClaudeClient')
    @patch('tools.create_blog_draft_tool.yaml.safe_load')
    @patch('builtins.open')
    def test_handles_bad_date_in_scores(
        self, mock_open, mock_yaml, mock_claude_cls, mock_draft
    ):
        mock_yaml.return_value = {
            'claude_drafter': {'model': 'x', 'temperature': 0.5, 'max_tokens': 4096}
        }
        mock_claude = MagicMock()
        mock_claude.send_message.return_value = json.dumps(mock_draft)
        mock_claude_cls.return_value = mock_claude

        tool = CreateBlogDraftTool()
        tool.claude_client = mock_claude
        # Score with unparseable date
        scores = [{'date': 'not-a-date', 'completed': True}]
        result = tool.execute(CreateBlogDraftInput(summaries=[], scores=scores))
        assert result.title == mock_draft['title']

    @patch('tools.create_blog_draft_tool.ClaudeClient')
    @patch('tools.create_blog_draft_tool.yaml.safe_load')
    @patch('builtins.open')
    def test_prompt_with_no_scores_no_summaries(
        self, mock_open, mock_yaml, mock_claude_cls, mock_draft
    ):
        mock_yaml.return_value = {
            'claude_drafter': {'model': 'x', 'temperature': 0.5, 'max_tokens': 4096}
        }
        mock_claude = MagicMock()
        mock_claude.send_message.return_value = json.dumps(mock_draft)
        mock_claude_cls.return_value = mock_claude

        tool = CreateBlogDraftTool()
        tool.claude_client = mock_claude
        tool.execute(CreateBlogDraftInput(summaries=[], scores=[]))

        prompt = mock_claude.send_message.call_args[0][0]
        assert 'None.' in prompt  # Both sections say "None."

    @patch('tools.create_blog_draft_tool.ClaudeClient')
    @patch('tools.create_blog_draft_tool.yaml.safe_load')
    @patch('builtins.open')
    def test_prompt_includes_scheduled_games(
        self, mock_open, mock_yaml, mock_claude_cls, mock_draft
    ):
        mock_yaml.return_value = {
            'claude_drafter': {'model': 'x', 'temperature': 0.5, 'max_tokens': 4096}
        }
        mock_claude = MagicMock()
        mock_claude.send_message.return_value = json.dumps(mock_draft)
        mock_claude_cls.return_value = mock_claude

        tool = CreateBlogDraftTool()
        tool.claude_client = mock_claude
        # Future scheduled game
        scores = [{'date': '2099-12-31T19:00:00Z', 'completed': False}]
        tool.execute(CreateBlogDraftInput(summaries=[], scores=scores))

        prompt = mock_claude.send_message.call_args[0][0]
        assert '2099' in prompt

    @patch('tools.create_blog_draft_tool.ClaudeClient')
    @patch('tools.create_blog_draft_tool.yaml.safe_load')
    @patch('builtins.open')
    def test_rejection_feedback_in_initial_prompt(
        self, mock_open, mock_yaml, mock_claude_cls, mock_draft
    ):
        mock_yaml.return_value = {
            'claude_drafter': {'model': 'x', 'temperature': 0.5, 'max_tokens': 4096}
        }
        mock_claude = MagicMock()
        mock_claude.send_message.return_value = json.dumps(mock_draft)
        mock_claude_cls.return_value = mock_claude

        tool = CreateBlogDraftTool()
        tool.claude_client = mock_claude
        tool.execute(
            CreateBlogDraftInput(
                summaries=[],
                scores=[],
                rejection_feedback='Add more Cubs detail',
            )
        )

        prompt = mock_claude.send_message.call_args[0][0]
        assert 'Add more Cubs detail' in prompt

    @patch('tools.create_blog_draft_tool.ClaudeClient')
    @patch('tools.create_blog_draft_tool.yaml.safe_load')
    @patch('builtins.open')
    def test_rejection_feedback_in_revision_prompt(
        self, mock_open, mock_yaml, mock_claude_cls, mock_draft
    ):
        mock_yaml.return_value = {
            'claude_drafter': {'model': 'x', 'temperature': 0.5, 'max_tokens': 4096}
        }
        mock_claude = MagicMock()
        mock_claude.send_message.return_value = json.dumps(mock_draft)
        mock_claude_cls.return_value = mock_claude

        tool = CreateBlogDraftTool()
        tool.claude_client = mock_claude
        tool.execute(
            CreateBlogDraftInput(
                summaries=[],
                scores=[],
                current_draft='<h1>Old</h1>',
                revision_notes={'seo': ['Fix']},
                rejection_feedback='More detail please',
            )
        )

        prompt = mock_claude.send_message.call_args[0][0]
        assert 'More detail please' in prompt
        assert 'CURRENT DRAFT' in prompt
