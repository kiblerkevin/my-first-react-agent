"""Tests for agent/base_agent.py."""

import json
from unittest.mock import MagicMock

from agent.base_agent import BaseAgent
from agent.context_window import ContextWindow


class TestBaseAgent:
    """Tests for BaseAgent tool execution and limits."""

    def _make_agent(self, max_tool_calls=None, force_first_tool=None):
        context = ContextWindow(conversation_history=[])
        client = MagicMock()
        agent = BaseAgent(
            context=context,
            claude_client=client,
            max_tool_calls=max_tool_calls,
            force_first_tool=force_first_tool,
        )
        return agent, client

    def test_execute_tool_success(self):
        agent, _ = self._make_agent()
        mock_tool = MagicMock()
        mock_tool.input_model.model_validate.return_value = MagicMock()
        mock_tool.execute.return_value = MagicMock(model_dump=lambda: {'result': 'ok'})
        agent.tools = {'test_tool': mock_tool}

        result = agent._execute_tool('test_tool', {'key': 'val'})
        parsed = json.loads(result)
        assert parsed == {'result': 'ok'}

    def test_execute_tool_not_found(self):
        agent, _ = self._make_agent()
        agent.tools = {}
        result = agent._execute_tool('missing_tool', {})
        assert 'not found' in result

    def test_tool_call_limit_stops_agent(self):
        agent, client = self._make_agent(max_tool_calls=1)
        agent.tool_call_count = 1  # simulate already at limit
        from agent.context_window import UserMessage
        agent.context.add(UserMessage(content='test'))
        result = agent.act()
        assert 'limit reached' in result.lower()

    def test_inject_required_context(self):
        agent, _ = self._make_agent()
        agent.required_tool_context = {'my_tool': {'field_a': 'injected_value'}}
        tool_input = {'field_b': 'existing'}
        result = agent._inject_required_context('my_tool', tool_input)
        assert result['field_a'] == 'injected_value'
        assert result['field_b'] == 'existing'

    def test_inject_required_context_does_not_overwrite(self):
        agent, _ = self._make_agent()
        agent.required_tool_context = {'my_tool': {'field_a': 'injected'}}
        tool_input = {'field_a': 'user_provided'}
        result = agent._inject_required_context('my_tool', tool_input)
        assert result['field_a'] == 'user_provided'

    def test_force_first_tool_sets_tool_choice(self):
        agent, client = self._make_agent(force_first_tool='create_blog_draft')
        # Mock a text response so act() returns
        mock_block = MagicMock()
        mock_block.type = 'text'
        mock_block.text = 'Done'
        mock_response = MagicMock(content=[mock_block])
        client.send_messages_with_tools.return_value = mock_response

        agent.tools = {'create_blog_draft': MagicMock()}
        agent.act()

        call_kwargs = client.send_messages_with_tools.call_args[1]
        assert call_kwargs.get('tool_choice') == {'type': 'tool', 'name': 'create_blog_draft'}


class TestBaseAgentToolUseLoop:
    """Tests for the full tool-use loop in BaseAgent.act()."""

    def test_executes_tool_and_recurses(self):
        """When Claude returns a tool_use block, agent executes it and calls act() again."""
        context = ContextWindow(conversation_history=[])
        client = MagicMock()
        agent = BaseAgent(context=context, claude_client=client, max_tool_calls=5)

        # First response: tool_use block
        tool_block = MagicMock()
        tool_block.type = 'tool_use'
        tool_block.name = 'test_tool'
        tool_block.input = {'key': 'val'}
        first_response = MagicMock(content=[tool_block])

        # Second response: text block (stops recursion)
        text_block = MagicMock()
        text_block.type = 'text'
        text_block.text = 'Final answer'
        second_response = MagicMock(content=[text_block])

        client.send_messages_with_tools.side_effect = [first_response, second_response]

        # Register a mock tool
        mock_tool = MagicMock()
        mock_tool.input_model.model_validate.return_value = MagicMock()
        mock_tool.execute.return_value = MagicMock(model_dump=lambda: {'result': 'ok'})
        agent.tools = {'test_tool': mock_tool}

        from agent.context_window import UserMessage
        agent.context.add(UserMessage(content='do something'))
        result = agent.act()

        assert result == 'Final answer'
        assert agent.tool_call_count == 1
        mock_tool.execute.assert_called_once()

    def test_stops_mid_response_when_limit_reached(self):
        """When limit is hit mid-response, agent sends error and recurses."""
        context = ContextWindow(conversation_history=[])
        client = MagicMock()
        agent = BaseAgent(context=context, claude_client=client, max_tool_calls=1)
        agent.tool_call_count = 0

        # Response with two tool_use blocks — second should be blocked
        tool_block_1 = MagicMock()
        tool_block_1.type = 'tool_use'
        tool_block_1.name = 'tool_a'
        tool_block_1.input = {}

        tool_block_2 = MagicMock()
        tool_block_2.type = 'tool_use'
        tool_block_2.name = 'tool_b'
        tool_block_2.input = {}

        first_response = MagicMock(content=[tool_block_1, tool_block_2])

        # After the error result, Claude returns text
        text_block = MagicMock()
        text_block.type = 'text'
        text_block.text = 'Best result'
        second_response = MagicMock(content=[text_block])

        client.send_messages_with_tools.side_effect = [first_response, second_response]

        mock_tool = MagicMock()
        mock_tool.input_model.model_validate.return_value = MagicMock()
        mock_tool.execute.return_value = MagicMock(model_dump=lambda: {'r': 1})
        agent.tools = {'tool_a': mock_tool, 'tool_b': mock_tool}

        from agent.context_window import UserMessage
        agent.context.add(UserMessage(content='test'))
        result = agent.act()

        assert agent.tool_call_count == 1  # only first tool executed
        assert 'limit reached' in result.lower()

    def test_revision_tracking_stores_draft_output(self):
        """Revision tracking captures draft output for injection on next call."""
        context = ContextWindow(conversation_history=[])
        client = MagicMock()
        agent = BaseAgent(
            context=context, claude_client=client, max_tool_calls=5,
            revision_tracking={'draft_tool': 'create_draft', 'evaluate_tool': 'evaluate'},
        )

        draft_json = json.dumps({'title': 'Test', 'content': 'Draft content here'})
        agent._track_revision_output('create_draft', draft_json)

        assert agent._last_draft_output is not None
        assert agent._last_draft_output['title'] == 'Test'

    def test_revision_tracking_stores_eval_suggestions(self):
        """Revision tracking captures evaluation suggestions."""
        context = ContextWindow(conversation_history=[])
        client = MagicMock()
        agent = BaseAgent(
            context=context, claude_client=client, max_tool_calls=5,
            revision_tracking={'draft_tool': 'create_draft', 'evaluate_tool': 'evaluate'},
        )

        eval_json = json.dumps({'improvement_suggestions': {'seo': ['Fix title']}})
        agent._track_revision_output('evaluate', eval_json)

        assert agent._last_eval_suggestions == {'seo': ['Fix title']}

    def test_inject_revision_context_adds_draft_and_notes(self):
        """On subsequent draft calls, previous draft and suggestions are injected."""
        context = ContextWindow(conversation_history=[])
        client = MagicMock()
        agent = BaseAgent(
            context=context, claude_client=client, max_tool_calls=5,
            revision_tracking={'draft_tool': 'create_draft', 'evaluate_tool': 'evaluate'},
        )
        agent._last_draft_output = {'content': 'Previous draft HTML'}
        agent._last_eval_suggestions = {'seo': ['Shorten title']}

        tool_input = {'summaries': [], 'scores': []}
        result = agent._inject_revision_context('create_draft', tool_input)

        assert result['current_draft'] == 'Previous draft HTML'
        assert result['revision_notes'] == {'seo': ['Shorten title']}

    def test_limit_extension_for_final_evaluation(self):
        """Agent extends limit by 1 if last tool was a draft (allows final eval)."""
        context = ContextWindow(conversation_history=[])
        client = MagicMock()
        agent = BaseAgent(
            context=context, claude_client=client, max_tool_calls=2,
            revision_tracking={'draft_tool': 'create_draft', 'evaluate_tool': 'evaluate'},
        )
        agent.tool_call_count = 2
        agent._last_tool_name = 'create_draft'

        from agent.context_window import UserMessage
        agent.context.add(UserMessage(content='test'))

        # Should extend limit, not stop
        text_block = MagicMock()
        text_block.type = 'text'
        text_block.text = 'Extended'
        client.send_messages_with_tools.return_value = MagicMock(content=[text_block])

        result = agent.act()
        assert agent.max_tool_calls == 3
        assert result == 'Extended'

    def test_send_message_adds_to_context(self):
        """send_message adds user and assistant messages to context."""
        context = ContextWindow(conversation_history=[])
        client = MagicMock()
        agent = BaseAgent(context=context, claude_client=client)

        text_block = MagicMock()
        text_block.type = 'text'
        text_block.text = 'Response'
        client.send_messages_with_tools.return_value = MagicMock(content=[text_block])
        agent.tools = {}

        result = agent.send_message('Hello')

        assert result == 'Response'
        assert len(context.conversation_history) == 2  # user + assistant


class TestBaseAgentRemainingGaps:
    """Tests for remaining uncovered lines in BaseAgent."""

    def test_act_returns_empty_string_when_no_text_block(self):
        """Line 188: returns '' when response has no text blocks."""
        context = ContextWindow(conversation_history=[])
        client = MagicMock()
        agent = BaseAgent(context=context, claude_client=client)

        # Response with no tool_use and no text blocks
        empty_block = MagicMock()
        empty_block.type = 'image'
        delattr(empty_block, 'text')
        response = MagicMock(content=[empty_block])
        client.send_messages_with_tools.return_value = response

        from agent.context_window import UserMessage
        agent.context.add(UserMessage(content='test'))
        result = agent.act()
        assert result == ''

    def test_inject_revision_context_no_config(self):
        """Line 229: returns input unchanged when no revision config."""
        context = ContextWindow(conversation_history=[])
        client = MagicMock()
        agent = BaseAgent(context=context, claude_client=client)

        tool_input = {'key': 'val'}
        result = agent._inject_revision_context('any_tool', tool_input)
        assert result == {'key': 'val'}

    def test_track_revision_output_invalid_json(self):
        """Lines 261-262: handles invalid JSON gracefully."""
        context = ContextWindow(conversation_history=[])
        client = MagicMock()
        agent = BaseAgent(
            context=context, claude_client=client,
            revision_tracking={'draft_tool': 'draft', 'evaluate_tool': 'eval'},
        )
        # Should not raise
        agent._track_revision_output('draft', 'not valid json')
        assert agent._last_draft_output is None

    def test_execute_tool_handles_exception(self):
        """Lines 291-292: returns error string on tool execution failure."""
        context = ContextWindow(conversation_history=[])
        client = MagicMock()
        agent = BaseAgent(context=context, claude_client=client)

        mock_tool = MagicMock()
        mock_tool.input_model.model_validate.side_effect = ValueError('bad input')
        agent.tools = {'broken_tool': mock_tool}

        result = agent._execute_tool('broken_tool', {'x': 1})
        assert 'Error executing tool broken_tool' in result

    def test_print_tool_use(self, capsys):
        """Line 300: prints tool use details."""
        context = ContextWindow(conversation_history=[])
        client = MagicMock()
        agent = BaseAgent(context=context, claude_client=client)

        from agent.context_window import ToolUse
        tool_use = ToolUse(id='1', name='test_tool', input={'key': 'val'})
        agent._print_tool_use(tool_use)

        captured = capsys.readouterr()
        assert 'test_tool' in captured.out
        assert 'key' in captured.out

    def test_print_tool_result(self, capsys):
        """Line 308: prints tool result details."""
        context = ContextWindow(conversation_history=[])
        client = MagicMock()
        agent = BaseAgent(context=context, claude_client=client)

        from agent.context_window import ToolResult
        tool_result = ToolResult(tool_use_id='1', content='result data', is_error=False)
        agent._print_tool_result(tool_result)

        captured = capsys.readouterr()
        assert 'result data' in captured.out


    def test_inject_revision_context_non_draft_tool(self):
        """Line 229: returns input unchanged for non-draft tool."""
        context = ContextWindow(conversation_history=[])
        client = MagicMock()
        agent = BaseAgent(
            context=context, claude_client=client,
            revision_tracking={'draft_tool': 'create_draft', 'evaluate_tool': 'evaluate'},
        )
        agent._last_draft_output = {'content': 'something'}

        tool_input = {'data': 'x'}
        result = agent._inject_revision_context('evaluate', tool_input)
        assert result == {'data': 'x'}  # unchanged
