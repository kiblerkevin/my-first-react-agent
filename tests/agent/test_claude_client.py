"""Tests for agent/claude_client.py."""

from unittest.mock import MagicMock, patch

from agent.claude_client import ClaudeClient


@patch('agent.claude_client.yaml.safe_load')
@patch('builtins.open')
@patch('agent.claude_client.Anthropic')
def _make_client(mock_anthropic, mock_open, mock_yaml, system_prompt='Test'):
    mock_yaml.side_effect = [
        {'claude': {'model': 'test-model', 'temperature': 0.5, 'max_tokens': 1024}},
        {'rate_limiting': {'max_retries': 2, 'base_delay_seconds': 0.01}},
    ]
    client = ClaudeClient(system_prompt=system_prompt)
    return client, mock_anthropic.return_value


class TestClaudeClientSendMessage:
    """Tests for ClaudeClient.send_message."""

    def test_returns_text_on_success(self):
        client, mock_api = _make_client()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='Hello world')]
        mock_api.messages.create.return_value = mock_response

        result = client.send_message('Hi')

        assert result == 'Hello world'
        mock_api.messages.create.assert_called_once()

    @patch('agent.claude_client.time.sleep')
    def test_retries_on_rate_limit(self, mock_sleep):
        client, mock_api = _make_client()
        from anthropic import RateLimitError

        error_response = MagicMock(status_code=429)
        error_response.headers = {}
        rate_error = RateLimitError.__new__(RateLimitError)
        rate_error.response = error_response
        rate_error.message = 'rate limited'

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='OK')]
        mock_api.messages.create.side_effect = [rate_error, mock_response]

        result = client.send_message('Hi')

        assert result == 'OK'
        assert mock_api.messages.create.call_count == 2
        mock_sleep.assert_called_once()

    @patch('agent.claude_client.time.sleep')
    def test_raises_after_max_retries_no_fallback(self, mock_sleep):
        client, mock_api = _make_client()
        client._fallback_config = {}  # no fallback
        from anthropic import RateLimitError

        error_response = MagicMock(status_code=429)
        error_response.headers = {}
        rate_error = RateLimitError.__new__(RateLimitError)
        rate_error.response = error_response
        rate_error.message = 'rate limited'

        mock_api.messages.create.side_effect = rate_error

        import pytest

        with pytest.raises(Exception, match='no fallback configured'):
            client.send_message('Hi')

        assert mock_api.messages.create.call_count == 3  # initial + 2 retries


class TestClaudeClientSendMessagesWithTools:
    """Tests for ClaudeClient.send_messages_with_tools."""

    def test_passes_tool_choice(self):
        client, mock_api = _make_client()
        mock_response = MagicMock()
        mock_api.messages.create.return_value = mock_response

        client.send_messages_with_tools(
            messages=[{'role': 'user', 'content': 'test'}],
            tools=[{'name': 'my_tool', 'description': 'x', 'input_schema': {}}],
            tool_choice={'type': 'tool', 'name': 'my_tool'},
        )

        call_kwargs = mock_api.messages.create.call_args[1]
        assert call_kwargs['tool_choice'] == {'type': 'tool', 'name': 'my_tool'}

    def test_omits_tool_choice_when_none(self):
        client, mock_api = _make_client()
        mock_response = MagicMock()
        mock_api.messages.create.return_value = mock_response

        client.send_messages_with_tools(
            messages=[{'role': 'user', 'content': 'test'}],
            tools=[],
        )

        call_kwargs = mock_api.messages.create.call_args[1]
        assert 'tool_choice' not in call_kwargs


class TestClaudeClientToolsRetry:
    """Tests for send_messages_with_tools retry and error handling."""

    @patch('agent.claude_client.time.sleep')
    def test_retries_on_rate_limit_with_tools(self, mock_sleep):
        client, mock_api = _make_client()
        from anthropic import RateLimitError

        error_response = MagicMock(status_code=429)
        error_response.headers = {}
        rate_error = RateLimitError.__new__(RateLimitError)
        rate_error.response = error_response
        rate_error.message = 'rate limited'

        mock_response = MagicMock()
        mock_api.messages.create.side_effect = [rate_error, mock_response]

        result = client.send_messages_with_tools(
            messages=[{'role': 'user', 'content': 'test'}],
            tools=[],
        )

        assert result == mock_response
        assert mock_api.messages.create.call_count == 2
        mock_sleep.assert_called_once()

    @patch('agent.claude_client.time.sleep')
    def test_raises_after_max_retries_with_tools_no_fallback(self, mock_sleep):
        client, mock_api = _make_client()
        client._fallback_config = {}  # no fallback
        from anthropic import RateLimitError

        error_response = MagicMock(status_code=429)
        error_response.headers = {}
        rate_error = RateLimitError.__new__(RateLimitError)
        rate_error.response = error_response
        rate_error.message = 'rate limited'

        mock_api.messages.create.side_effect = rate_error

        import pytest

        with pytest.raises(Exception, match='no fallback configured'):
            client.send_messages_with_tools(
                messages=[{'role': 'user', 'content': 'test'}],
                tools=[],
            )

    def test_raises_on_generic_exception_with_tools(self):
        client, mock_api = _make_client()
        mock_api.messages.create.side_effect = ValueError('bad input')

        import pytest

        with pytest.raises(Exception, match='Failed to create message'):
            client.send_messages_with_tools(
                messages=[{'role': 'user', 'content': 'test'}],
                tools=[],
            )

    def test_raises_on_generic_exception_send_message(self):
        client, mock_api = _make_client()
        mock_api.messages.create.side_effect = ValueError('bad input')

        import pytest

        with pytest.raises(Exception, match='Failed to create message'):
            client.send_message('test')


class TestClaudeClientFallback:
    """Tests for Gemini fallback on Claude API errors."""

    @patch('agent.claude_client.time.sleep')
    def test_falls_back_on_connection_error(self, mock_sleep):
        client, mock_api = _make_client()
        from anthropic import APIConnectionError

        mock_api.messages.create.side_effect = APIConnectionError(request=MagicMock())

        with patch.object(client, '_get_fallback_client') as mock_fb:
            mock_gemini = MagicMock()
            mock_gemini.send_message.return_value = 'Gemini response'
            mock_fb.return_value = mock_gemini

            result = client.send_message('Hi')
            assert result == 'Gemini response'
            mock_gemini.send_message.assert_called_once_with('Hi')

    @patch('agent.claude_client.time.sleep')
    def test_falls_back_on_auth_error(self, mock_sleep):
        client, mock_api = _make_client()
        from anthropic import AuthenticationError

        error_response = MagicMock(status_code=401)
        error_response.headers = {}
        auth_error = AuthenticationError.__new__(AuthenticationError)
        auth_error.response = error_response
        auth_error.message = 'invalid key'
        mock_api.messages.create.side_effect = auth_error

        with patch.object(client, '_get_fallback_client') as mock_fb:
            mock_gemini = MagicMock()
            mock_gemini.send_message.return_value = 'Gemini fallback'
            mock_fb.return_value = mock_gemini

            result = client.send_message('Hi')
            assert result == 'Gemini fallback'

    @patch('agent.claude_client.time.sleep')
    def test_falls_back_on_internal_server_error(self, mock_sleep):
        client, mock_api = _make_client()
        from anthropic import InternalServerError

        error_response = MagicMock(status_code=500)
        error_response.headers = {}
        server_error = InternalServerError.__new__(InternalServerError)
        server_error.response = error_response
        server_error.message = 'internal error'
        mock_api.messages.create.side_effect = server_error

        with patch.object(client, '_get_fallback_client') as mock_fb:
            mock_gemini = MagicMock()
            mock_gemini.send_message.return_value = 'Gemini 500 fallback'
            mock_fb.return_value = mock_gemini

            result = client.send_message('Hi')
            assert result == 'Gemini 500 fallback'

    @patch('agent.claude_client.time.sleep')
    def test_falls_back_with_tools_on_connection_error(self, mock_sleep):
        client, mock_api = _make_client()
        from anthropic import APIConnectionError

        mock_api.messages.create.side_effect = APIConnectionError(request=MagicMock())

        with patch.object(client, '_get_fallback_client') as mock_fb:
            mock_gemini = MagicMock()
            mock_gemini.send_messages_with_tools.return_value = MagicMock()
            mock_fb.return_value = mock_gemini

            client.send_messages_with_tools(
                messages=[{'role': 'user', 'content': 'test'}],
                tools=[],
            )
            mock_gemini.send_messages_with_tools.assert_called_once()

    @patch('agent.claude_client.time.sleep')
    def test_rate_limit_exhaustion_triggers_fallback(self, mock_sleep):
        client, mock_api = _make_client()
        from anthropic import RateLimitError

        error_response = MagicMock(status_code=429)
        error_response.headers = {}
        rate_error = RateLimitError.__new__(RateLimitError)
        rate_error.response = error_response
        rate_error.message = 'rate limited'
        mock_api.messages.create.side_effect = rate_error

        with patch.object(client, '_get_fallback_client') as mock_fb:
            mock_gemini = MagicMock()
            mock_gemini.send_message.return_value = 'Gemini after rate limit'
            mock_fb.return_value = mock_gemini

            result = client.send_message('Hi')
            assert result == 'Gemini after rate limit'
            # Should have retried first
            assert mock_api.messages.create.call_count == 3  # initial + 2 retries

    def test_raises_when_no_fallback_configured(self):
        client, mock_api = _make_client()
        client._fallback_config = {}
        from anthropic import APIConnectionError

        mock_api.messages.create.side_effect = APIConnectionError(request=MagicMock())

        import pytest

        with pytest.raises(Exception, match='no fallback configured'):
            client.send_message('Hi')

    def test_raises_when_no_fallback_configured_with_tools(self):
        client, mock_api = _make_client()
        client._fallback_config = {}
        from anthropic import APIConnectionError

        mock_api.messages.create.side_effect = APIConnectionError(request=MagicMock())

        import pytest

        with pytest.raises(Exception, match='no fallback configured'):
            client.send_messages_with_tools(
                messages=[{'role': 'user', 'content': 'test'}],
                tools=[],
            )

    def test_get_fallback_client_returns_none_when_not_configured(self):
        client, _ = _make_client()
        client._fallback_config = {}
        assert client._get_fallback_client() is None

    @patch('agent.gemini_client.genai.Client')
    def test_get_fallback_client_returns_gemini(self, mock_genai):
        client, _ = _make_client()
        client._fallback_config = {'provider': 'gemini', 'model': 'gemini-2.5-flash'}
        fb = client._get_fallback_client()
        assert fb is not None
        assert fb.model == 'gemini-2.5-flash'
