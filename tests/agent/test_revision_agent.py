"""Tests for agent/revision_agent.py."""

import json
from unittest.mock import MagicMock, patch

from agent.context_window import ContextWindow, ToolResult, ToolResultMessage
from agent.revision_agent import RevisionAgent


class TestRevisionAgent:
    """Tests for RevisionAgent helper methods."""

    @patch('agent.revision_agent.yaml.safe_load')
    @patch('builtins.open')
    def test_build_message_includes_all_sections(
        self, mock_open, mock_yaml, mock_summaries, mock_scores
    ):
        mock_yaml.return_value = {
            'revision_loop': {'criterion_floors': {'accuracy': 7}, 'max_tool_calls': 6}
        }
        agent = RevisionAgent()
        msg = agent._build_message(mock_summaries, mock_scores)
        assert 'ARTICLE SUMMARIES' in msg
        assert 'GAME SCORES' in msg

    @patch('agent.revision_agent.yaml.safe_load')
    @patch('builtins.open')
    def test_build_message_includes_rejection_feedback(
        self, mock_open, mock_yaml, mock_summaries, mock_scores
    ):
        mock_yaml.return_value = {
            'revision_loop': {'criterion_floors': {'accuracy': 7}, 'max_tool_calls': 6}
        }
        agent = RevisionAgent()
        msg = agent._build_message(
            mock_summaries, mock_scores, rejection_feedback='Fix the title'
        )
        assert 'Fix the title' in msg

    @patch('agent.revision_agent.yaml.safe_load')
    @patch('builtins.open')
    def test_extract_results_finds_drafts_and_evaluations(
        self, mock_open, mock_yaml, mock_draft, mock_evaluation
    ):
        mock_yaml.return_value = {
            'revision_loop': {'criterion_floors': {'accuracy': 7}, 'max_tool_calls': 6}
        }
        agent = RevisionAgent()

        # Ensure content is > 100 chars for detection
        draft_with_long_content = dict(mock_draft)
        draft_with_long_content['content'] = 'x' * 150

        # Build a context with tool results
        context = ContextWindow(conversation_history=[])
        draft_result = ToolResult(
            tool_use_id='1', content=json.dumps(draft_with_long_content), is_error=False
        )
        eval_result = ToolResult(
            tool_use_id='2', content=json.dumps(mock_evaluation), is_error=False
        )
        context.conversation_history.append(ToolResultMessage(content=[draft_result]))
        context.conversation_history.append(ToolResultMessage(content=[eval_result]))

        results = agent._extract_results(context, 'Final response')
        assert results['best_draft']['title'] == mock_draft['title']
        assert (
            results['best_evaluation']['overall_score']
            == mock_evaluation['overall_score']
        )
        assert len(results['all_drafts']) == 1
        assert len(results['all_evaluations']) == 1

    @patch('agent.revision_agent.yaml.safe_load')
    @patch('builtins.open')
    def test_extract_results_handles_empty_history(self, mock_open, mock_yaml):
        mock_yaml.return_value = {
            'revision_loop': {'criterion_floors': {'accuracy': 7}, 'max_tool_calls': 6}
        }
        agent = RevisionAgent()
        context = ContextWindow(conversation_history=[])

        results = agent._extract_results(context, 'No tools called')
        assert results['best_draft']['title'] == ''
        assert results['best_evaluation']['overall_score'] == 0.0


class TestRevisionAgentRun:
    """Tests for RevisionAgent.run() full execution."""

    @patch('agent.revision_agent.BaseAgent')
    @patch('agent.revision_agent.EvaluateBlogPostTool')
    @patch('agent.revision_agent.CreateBlogDraftTool')
    @patch('agent.revision_agent.ClaudeClient')
    @patch('agent.revision_agent.yaml.safe_load')
    @patch('builtins.open')
    def test_run_returns_results(
        self,
        mock_open,
        mock_yaml,
        mock_claude_cls,
        mock_draft_cls,
        mock_eval_cls,
        mock_agent_cls,
        mock_summaries,
        mock_scores,
        mock_draft,
        mock_evaluation,
    ):
        mock_yaml.side_effect = [
            {
                'revision_loop': {
                    'criterion_floors': {'accuracy': 7},
                    'max_tool_calls': 6,
                }
            },
            {
                'claude_orchestrator': {
                    'model': 'test',
                    'temperature': 0.3,
                    'max_tokens': 2048,
                }
            },
        ]

        # Mock the BaseAgent to simulate tool call history
        mock_agent = MagicMock()
        mock_agent.tool_call_count = 4
        mock_agent.send_message.return_value = 'Done'

        # Build context with draft and eval results in history
        draft_with_content = dict(mock_draft)
        draft_with_content['content'] = 'x' * 150

        from agent.context_window import ContextWindow, ToolResult, ToolResultMessage

        context = ContextWindow(conversation_history=[])
        context.conversation_history.append(
            ToolResultMessage(
                content=[
                    ToolResult(
                        tool_use_id='1',
                        content=json.dumps(draft_with_content),
                        is_error=False,
                    )
                ]
            )
        )
        context.conversation_history.append(
            ToolResultMessage(
                content=[
                    ToolResult(
                        tool_use_id='2',
                        content=json.dumps(mock_evaluation),
                        is_error=False,
                    )
                ]
            )
        )

        mock_agent_cls.return_value = mock_agent
        mock_agent_cls.return_value.context = context
        # Patch so BaseAgent() returns our mock but _extract_results uses real context
        mock_agent_cls.side_effect = None
        mock_agent_cls.return_value = mock_agent

        agent = RevisionAgent()
        # Directly test with a patched _extract_results to avoid complex mock setup
        with patch.object(
            agent,
            '_extract_results',
            return_value={
                'best_draft': mock_draft,
                'best_evaluation': mock_evaluation,
                'all_drafts': [mock_draft],
                'all_evaluations': [mock_evaluation],
                'agent_response': 'Done',
            },
        ):
            result = agent.run(summaries=mock_summaries, scores=mock_scores)

        assert result['best_draft'] == mock_draft
        assert result['best_evaluation'] == mock_evaluation
        assert agent._last_tool_calls == 4

    @patch('agent.revision_agent.BaseAgent')
    @patch('agent.revision_agent.EvaluateBlogPostTool')
    @patch('agent.revision_agent.CreateBlogDraftTool')
    @patch('agent.revision_agent.ClaudeClient')
    @patch('agent.revision_agent.yaml.safe_load')
    @patch('builtins.open')
    def test_run_with_rejection_feedback(
        self,
        mock_open,
        mock_yaml,
        mock_claude_cls,
        mock_draft_cls,
        mock_eval_cls,
        mock_agent_cls,
        mock_summaries,
        mock_scores,
        mock_draft,
        mock_evaluation,
    ):
        mock_yaml.side_effect = [
            {
                'revision_loop': {
                    'criterion_floors': {'accuracy': 7},
                    'max_tool_calls': 6,
                }
            },
            {
                'claude_orchestrator': {
                    'model': 'test',
                    'temperature': 0.3,
                    'max_tokens': 2048,
                }
            },
        ]

        mock_agent = MagicMock()
        mock_agent.tool_call_count = 2
        mock_agent.send_message.return_value = 'Done with feedback'
        mock_agent_cls.return_value = mock_agent

        agent = RevisionAgent()
        with patch.object(
            agent,
            '_extract_results',
            return_value={
                'best_draft': mock_draft,
                'best_evaluation': mock_evaluation,
                'all_drafts': [mock_draft],
                'all_evaluations': [mock_evaluation],
                'agent_response': 'Done with feedback',
            },
        ):
            agent.run(
                summaries=mock_summaries,
                scores=mock_scores,
                rejection_feedback='Add more detail about the Cubs game',
            )

        # Verify rejection feedback was included in the message
        call_args = mock_agent.send_message.call_args[0][0]
        assert 'Add more detail about the Cubs game' in call_args


class TestRevisionAgentExtractEdgeCases:
    """Tests for _extract_results edge cases."""

    @patch('agent.revision_agent.yaml.safe_load')
    @patch('builtins.open')
    def test_skips_non_tool_result_items(self, mock_open, mock_yaml):
        """Line 174: skips items that aren't tool_result type."""
        mock_yaml.return_value = {
            'revision_loop': {'criterion_floors': {}, 'max_tool_calls': 6}
        }
        agent = RevisionAgent()

        context = ContextWindow(conversation_history=[])
        # Add a message with non-tool_result content
        context.conversation_history.append(
            ToolResultMessage(
                content=[
                    ToolResult(tool_use_id='1', content='not json', is_error=True),
                ]
            )
        )

        results = agent._extract_results(context, 'response')
        assert results['all_drafts'] == []
        assert results['all_evaluations'] == []

    @patch('agent.revision_agent.yaml.safe_load')
    @patch('builtins.open')
    def test_skips_invalid_json_in_tool_results(self, mock_open, mock_yaml):
        """Lines 178-179: handles invalid JSON in tool results."""
        mock_yaml.return_value = {
            'revision_loop': {'criterion_floors': {}, 'max_tool_calls': 6}
        }
        agent = RevisionAgent()

        context = ContextWindow(conversation_history=[])
        context.conversation_history.append(
            ToolResultMessage(
                content=[
                    ToolResult(
                        tool_use_id='1', content='{{invalid json', is_error=False
                    ),
                ]
            )
        )

        results = agent._extract_results(context, 'response')
        assert results['all_drafts'] == []

    @patch('agent.revision_agent.yaml.safe_load')
    @patch('builtins.open')
    def test_tied_scores_prefer_most_recent_draft(self, mock_open, mock_yaml):
        """When evaluations tie, the most recent draft should be selected."""
        mock_yaml.return_value = {
            'revision_loop': {'criterion_floors': {}, 'max_tool_calls': 6}
        }
        agent = RevisionAgent()

        draft1 = {'title': 'Draft 1', 'content': 'x' * 150, 'excerpt': '', 'teams_covered': []}
        draft2 = {'title': 'Draft 2', 'content': 'y' * 150, 'excerpt': '', 'teams_covered': []}
        eval1 = {'criteria_scores': {'accuracy': 8.5}, 'overall_score': 8.5}
        eval2 = {'criteria_scores': {'accuracy': 8.5}, 'overall_score': 8.5}

        context = ContextWindow(conversation_history=[])
        for draft, evaluation in [(draft1, eval1), (draft2, eval2)]:
            context.conversation_history.append(
                ToolResultMessage(content=[ToolResult(tool_use_id='d', content=json.dumps(draft), is_error=False)])
            )
            context.conversation_history.append(
                ToolResultMessage(content=[ToolResult(tool_use_id='e', content=json.dumps(evaluation), is_error=False)])
            )

        results = agent._extract_results(context, 'response')
        assert results['best_draft']['title'] == 'Draft 2'
        assert results['best_evaluation']['overall_score'] == 8.5
