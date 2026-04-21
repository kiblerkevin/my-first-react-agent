"""Tests for tools/evaluate_blog_post_tool.py."""

import json
from unittest.mock import MagicMock, patch

from models.inputs.evaluate_blog_post_input import EvaluateBlogPostInput
from tools.evaluate_blog_post_tool import EvaluateBlogPostTool


class TestEvaluateBlogPostTool:
    """Tests for EvaluateBlogPostTool.execute."""

    @patch('tools.evaluate_blog_post_tool.ClaudeClient')
    @patch('tools.evaluate_blog_post_tool.yaml.safe_load')
    @patch('builtins.open')
    def test_parses_evaluation_response(
        self, mock_open, mock_yaml, mock_claude_cls, mock_evaluation
    ):
        mock_yaml.return_value = {
            'claude_evaluator': {'model': 'x', 'temperature': 0.1, 'max_tokens': 2048}
        }
        mock_claude = MagicMock()
        mock_claude.send_message.return_value = json.dumps(mock_evaluation)
        mock_claude_cls.return_value = mock_claude

        tool = EvaluateBlogPostTool()
        tool.claude_client = mock_claude
        result = tool.execute(
            EvaluateBlogPostInput(
                title='Test',
                content='<h1>Test</h1>',
                excerpt='Test excerpt',
                summaries=[],
                scores=[],
            )
        )

        assert result.overall_score == 8.25
        assert result.criteria_scores['accuracy'] == 9.0
        assert 'seo' in result.improvement_suggestions

    @patch('tools.evaluate_blog_post_tool.ClaudeClient')
    @patch('tools.evaluate_blog_post_tool.yaml.safe_load')
    @patch('builtins.open')
    def test_handles_malformed_response(self, mock_open, mock_yaml, mock_claude_cls):
        mock_yaml.return_value = {
            'claude_evaluator': {'model': 'x', 'temperature': 0.1, 'max_tokens': 2048}
        }
        mock_claude = MagicMock()
        mock_claude.send_message.return_value = 'not valid json'
        mock_claude_cls.return_value = mock_claude

        tool = EvaluateBlogPostTool()
        tool.claude_client = mock_claude
        result = tool.execute(
            EvaluateBlogPostInput(
                title='Test',
                content='<h1>Test</h1>',
                excerpt='Test',
                summaries=[],
                scores=[],
            )
        )

        assert result.overall_score == 0.0
        assert result.evaluation_id != ''

    @patch('tools.evaluate_blog_post_tool.ClaudeClient')
    @patch('tools.evaluate_blog_post_tool.yaml.safe_load')
    @patch('builtins.open')
    def test_includes_rejection_feedback_in_prompt(
        self, mock_open, mock_yaml, mock_claude_cls, mock_evaluation
    ):
        mock_yaml.return_value = {
            'claude_evaluator': {'model': 'x', 'temperature': 0.1, 'max_tokens': 2048}
        }
        mock_claude = MagicMock()
        mock_claude.send_message.return_value = json.dumps(mock_evaluation)
        mock_claude_cls.return_value = mock_claude

        tool = EvaluateBlogPostTool()
        tool.claude_client = mock_claude
        tool.execute(
            EvaluateBlogPostInput(
                title='Test',
                content='<h1>Test</h1>',
                excerpt='Test',
                summaries=[],
                scores=[],
                rejection_feedback='Add more detail',
            )
        )

        call_args = mock_claude.send_message.call_args[0][0]
        assert 'Add more detail' in call_args


class TestEvaluateBlogPostToolEdgeCases:
    """Tests for edge cases in evaluation response parsing."""

    @patch('tools.evaluate_blog_post_tool.ClaudeClient')
    @patch('tools.evaluate_blog_post_tool.yaml.safe_load')
    @patch('builtins.open')
    def test_handles_string_improvement_suggestions(
        self, mock_open, mock_yaml, mock_claude_cls
    ):
        mock_yaml.return_value = {
            'claude_evaluator': {'model': 'x', 'temperature': 0.1, 'max_tokens': 2048}
        }
        mock_claude = MagicMock()
        # Return suggestions as strings instead of lists
        response = {
            'criteria_scores': {
                'accuracy': 8,
                'completeness': 7,
                'readability': 9,
                'seo': 6,
            },
            'criteria_reasoning': {
                'accuracy': 'OK',
                'completeness': 'OK',
                'readability': 'OK',
                'seo': 'OK',
            },
            'improvement_suggestions': {'seo': 'Shorten the title', 'accuracy': 42},
        }
        mock_claude.send_message.return_value = json.dumps(response)
        mock_claude_cls.return_value = mock_claude

        tool = EvaluateBlogPostTool()
        tool.claude_client = mock_claude
        result = tool.execute(
            EvaluateBlogPostInput(
                title='T',
                content='C',
                excerpt='E',
                summaries=[],
                scores=[],
            )
        )

        # String should be wrapped in list
        assert result.improvement_suggestions['seo'] == ['Shorten the title']
        # Non-string/non-list should be stringified
        assert result.improvement_suggestions['accuracy'] == ['42']
