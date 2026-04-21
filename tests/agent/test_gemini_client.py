"""Tests for agent/gemini_client.py."""

from unittest.mock import MagicMock, patch


class TestGeminiClientSendMessage:
    """Tests for GeminiClient.send_message."""

    @patch('agent.gemini_client.genai.Client')
    def test_returns_text(self, mock_client_cls):
        from agent.gemini_client import GeminiClient

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = 'Gemini says hello'
        mock_client.models.generate_content.return_value = mock_response
        mock_client_cls.return_value = mock_client

        client = GeminiClient(system_prompt='Be helpful', model='gemini-2.5-flash')
        result = client.send_message('Hi')

        assert result == 'Gemini says hello'
        mock_client.models.generate_content.assert_called_once()

    @patch('agent.gemini_client.genai.Client')
    def test_passes_system_prompt(self, mock_client_cls):
        from agent.gemini_client import GeminiClient

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = 'OK'
        mock_client.models.generate_content.return_value = mock_response
        mock_client_cls.return_value = mock_client

        client = GeminiClient(system_prompt='You are a sports writer')
        client.send_message('Write something')

        call_kwargs = mock_client.models.generate_content.call_args[1]
        assert call_kwargs['config']['system_instruction'] == 'You are a sports writer'


class TestGeminiClientSendMessagesWithTools:
    """Tests for GeminiClient.send_messages_with_tools."""

    @patch('agent.gemini_client.genai.Client')
    def test_returns_adapted_response(self, mock_client_cls):
        from agent.gemini_client import GeminiClient

        mock_client = MagicMock()

        # Mock a text response
        part = MagicMock()
        part.function_call = None
        part.text = 'Done'
        candidate = MagicMock()
        candidate.content.parts = [part]
        mock_response = MagicMock()
        mock_response.candidates = [candidate]
        mock_client.models.generate_content.return_value = mock_response
        mock_client_cls.return_value = mock_client

        client = GeminiClient(system_prompt='Test')
        result = client.send_messages_with_tools(
            messages=[{'role': 'user', 'content': 'test'}],
            tools=[{'name': 'my_tool', 'description': 'x', 'input_schema': {}}],
        )

        assert result.content[0].text == 'Done'

    @patch('agent.gemini_client.genai.Client')
    def test_passes_tool_choice(self, mock_client_cls):
        from agent.gemini_client import GeminiClient

        mock_client = MagicMock()
        part = MagicMock()
        part.function_call = None
        part.text = 'OK'
        candidate = MagicMock()
        candidate.content.parts = [part]
        mock_response = MagicMock()
        mock_response.candidates = [candidate]
        mock_client.models.generate_content.return_value = mock_response
        mock_client_cls.return_value = mock_client

        client = GeminiClient(system_prompt='Test')
        client.send_messages_with_tools(
            messages=[{'role': 'user', 'content': 'test'}],
            tools=[{'name': 't', 'description': 'x', 'input_schema': {}}],
            tool_choice={'type': 'tool', 'name': 't'},
        )

        call_kwargs = mock_client.models.generate_content.call_args[1]
        assert 'tool_config' in call_kwargs['config']

    @patch('agent.gemini_client.genai.Client')
    def test_handles_empty_tools(self, mock_client_cls):
        from agent.gemini_client import GeminiClient

        mock_client = MagicMock()
        part = MagicMock()
        part.function_call = None
        part.text = 'No tools'
        candidate = MagicMock()
        candidate.content.parts = [part]
        mock_response = MagicMock()
        mock_response.candidates = [candidate]
        mock_client.models.generate_content.return_value = mock_response
        mock_client_cls.return_value = mock_client

        client = GeminiClient(system_prompt='Test')
        result = client.send_messages_with_tools(
            messages=[{'role': 'user', 'content': 'test'}],
            tools=[],
        )

        assert result.content[0].text == 'No tools'
