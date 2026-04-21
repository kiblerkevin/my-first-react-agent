"""Tests for agent/gemini_adapter.py."""

from unittest.mock import MagicMock

from agent.gemini_adapter import (
    TextBlock,
    ToolUseBlock,
    adapt_messages,
    adapt_response,
    adapt_tools,
)


class TestAdaptTools:
    """Tests for adapt_tools."""

    def test_converts_claude_tools_to_gemini(self):
        claude_tools = [
            {
                'name': 'my_tool',
                'description': 'Does stuff',
                'input_schema': {
                    'type': 'object',
                    'properties': {'key': {'type': 'string'}},
                    'required': ['key'],
                },
            }
        ]
        result = adapt_tools(claude_tools)
        assert len(result) == 1
        assert result[0]['name'] == 'my_tool'
        assert result[0]['description'] == 'Does stuff'
        assert result[0]['parameters']['properties'] == {'key': {'type': 'string'}}
        assert result[0]['parameters']['required'] == ['key']

    def test_handles_empty_tools(self):
        assert adapt_tools([]) == []

    def test_handles_missing_schema(self):
        result = adapt_tools([{'name': 'bare', 'description': 'x'}])
        assert result[0]['parameters']['type'] == 'object'


class TestAdaptResponse:
    """Tests for adapt_response."""

    def test_adapts_text_response(self):
        part = MagicMock()
        part.function_call = None
        part.text = 'Hello world'

        candidate = MagicMock()
        candidate.content.parts = [part]

        response = MagicMock()
        response.candidates = [candidate]

        result = adapt_response(response)
        assert len(result.content) == 1
        assert isinstance(result.content[0], TextBlock)
        assert result.content[0].text == 'Hello world'

    def test_adapts_tool_use_response(self):
        fc = MagicMock()
        fc.name = 'my_tool'
        fc.args = {'key': 'val'}

        part = MagicMock()
        part.function_call = fc
        part.text = None

        candidate = MagicMock()
        candidate.content.parts = [part]

        response = MagicMock()
        response.candidates = [candidate]

        result = adapt_response(response)
        assert len(result.content) == 1
        assert isinstance(result.content[0], ToolUseBlock)
        assert result.content[0].name == 'my_tool'
        assert result.content[0].input == {'key': 'val'}

    def test_adapts_mixed_response(self):
        text_part = MagicMock()
        text_part.function_call = None
        text_part.text = 'Thinking...'

        fc = MagicMock()
        fc.name = 'tool_a'
        fc.args = {}
        tool_part = MagicMock()
        tool_part.function_call = fc
        tool_part.text = None

        candidate = MagicMock()
        candidate.content.parts = [text_part, tool_part]

        response = MagicMock()
        response.candidates = [candidate]

        result = adapt_response(response)
        assert len(result.content) == 2
        assert isinstance(result.content[0], TextBlock)
        assert isinstance(result.content[1], ToolUseBlock)

    def test_handles_empty_response(self):
        response = MagicMock()
        response.candidates = []
        result = adapt_response(response)
        assert len(result.content) == 1
        assert result.content[0].text == ''

    def test_handles_none_response(self):
        result = adapt_response(None)
        assert len(result.content) == 1
        assert result.content[0].text == ''

    def test_handles_no_parts(self):
        candidate = MagicMock()
        candidate.content.parts = []

        response = MagicMock()
        response.candidates = [candidate]
        response.text = 'fallback text'

        result = adapt_response(response)
        assert result.content[0].text == 'fallback text'


class TestAdaptMessages:
    """Tests for adapt_messages."""

    def test_converts_user_and_assistant_messages(self):
        messages = [
            {'role': 'user', 'content': 'Hello'},
            {'role': 'assistant', 'content': 'Hi there'},
        ]
        system, contents = adapt_messages(messages, 'Be helpful')
        assert system == 'Be helpful'
        assert len(contents) == 2
        assert contents[0]['role'] == 'user'
        assert contents[1]['role'] == 'model'

    def test_converts_tool_use_content(self):
        messages = [
            {
                'role': 'assistant',
                'content': [{'type': 'tool_use', 'name': 'my_tool', 'input': {'x': 1}}],
            }
        ]
        _, contents = adapt_messages(messages, '')
        assert 'function_call' in contents[0]['parts'][0]

    def test_converts_tool_result_content(self):
        messages = [
            {
                'role': 'user',
                'content': [{'type': 'tool_result', 'content': '{"result": "ok"}'}],
            }
        ]
        _, contents = adapt_messages(messages, '')
        assert 'function_response' in contents[0]['parts'][0]

    def test_handles_text_type_in_list(self):
        messages = [{'role': 'user', 'content': [{'type': 'text', 'text': 'hello'}]}]
        _, contents = adapt_messages(messages, '')
        assert contents[0]['parts'][0] == {'text': 'hello'}

    def test_handles_unknown_type_in_list(self):
        messages = [{'role': 'user', 'content': [{'type': 'image', 'data': 'abc'}]}]
        _, contents = adapt_messages(messages, '')
        assert 'text' in contents[0]['parts'][0]

    def test_handles_non_dict_in_list(self):
        messages = [{'role': 'user', 'content': [42]}]
        _, contents = adapt_messages(messages, '')
        assert contents[0]['parts'][0] == {'text': '42'}
