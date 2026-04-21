"""Tests for utils/http.py."""

from unittest.mock import MagicMock, patch

from utils.http import rate_limited_request


class TestRateLimitedRequest:
    """Tests for rate_limited_request."""

    @patch('utils.http._get_config')
    @patch('utils.http.requests.request')
    def test_success_on_first_try(self, mock_request, mock_config):
        mock_config.return_value = {'max_retries': 3, 'base_delay_seconds': 0.01}
        mock_response = MagicMock(status_code=200)
        mock_request.return_value = mock_response

        result = rate_limited_request('GET', 'https://example.com')

        assert result.status_code == 200
        mock_request.assert_called_once()

    @patch('utils.http._get_config')
    @patch('utils.http.requests.request')
    @patch('utils.http.time.sleep')
    def test_retries_on_429(self, mock_sleep, mock_request, mock_config):
        mock_config.return_value = {'max_retries': 3, 'base_delay_seconds': 0.01}
        mock_429 = MagicMock(status_code=429, headers={})
        mock_200 = MagicMock(status_code=200)
        mock_request.side_effect = [mock_429, mock_200]

        result = rate_limited_request('GET', 'https://example.com')

        assert result.status_code == 200
        assert mock_request.call_count == 2
        mock_sleep.assert_called_once()

    @patch('utils.http._get_config')
    @patch('utils.http.requests.request')
    @patch('utils.http.time.sleep')
    def test_respects_retry_after_header(self, mock_sleep, mock_request, mock_config):
        mock_config.return_value = {'max_retries': 3, 'base_delay_seconds': 0.01}
        mock_429 = MagicMock(status_code=429, headers={'Retry-After': '2.5'})
        mock_200 = MagicMock(status_code=200)
        mock_request.side_effect = [mock_429, mock_200]

        rate_limited_request('GET', 'https://example.com')

        mock_sleep.assert_called_once_with(2.5)

    @patch('utils.http._get_config')
    @patch('utils.http.requests.request')
    @patch('utils.http.time.sleep')
    def test_returns_429_after_max_retries(self, mock_sleep, mock_request, mock_config):
        mock_config.return_value = {'max_retries': 2, 'base_delay_seconds': 0.01}
        mock_429 = MagicMock(status_code=429, headers={})
        mock_request.return_value = mock_429

        result = rate_limited_request('GET', 'https://example.com')

        assert result.status_code == 429
        assert mock_request.call_count == 3  # initial + 2 retries

    @patch('utils.http._get_config')
    @patch('utils.http.requests.request')
    def test_passes_kwargs_through(self, mock_request, mock_config):
        mock_config.return_value = {'max_retries': 3, 'base_delay_seconds': 0.01}
        mock_request.return_value = MagicMock(status_code=200)

        rate_limited_request(
            'POST', 'https://example.com', json={'key': 'val'}, timeout=10
        )

        mock_request.assert_called_once_with(
            'POST', 'https://example.com', json={'key': 'val'}, timeout=10
        )


class TestRateLimitedRequestEdgeCases:
    """Edge case tests for rate_limited_request."""

    @patch('utils.http._get_config')
    @patch('utils.http.requests.request')
    @patch('utils.http.time.sleep')
    def test_invalid_retry_after_uses_exponential_backoff(
        self, mock_sleep, mock_request, mock_config
    ):
        mock_config.return_value = {'max_retries': 3, 'base_delay_seconds': 1.0}
        mock_429 = MagicMock(status_code=429, headers={'Retry-After': 'invalid-value'})
        mock_200 = MagicMock(status_code=200)
        mock_request.side_effect = [mock_429, mock_200]

        rate_limited_request('GET', 'https://example.com')

        # Should use base_delay * 2^0 = 1.0 since Retry-After is invalid
        mock_sleep.assert_called_once_with(1.0)


def test_get_config_loads_from_file():
    """Test that _get_config reads from the orchestration yaml file."""
    import utils.http as http_module

    # Reset the cached config
    original = http_module._rate_limit_config
    http_module._rate_limit_config = None

    try:
        with (
            patch('builtins.open'),
            patch(
                'utils.http.yaml.safe_load',
                return_value={
                    'rate_limiting': {'max_retries': 5, 'base_delay_seconds': 2.0}
                },
            ),
        ):
            config = http_module._get_config()
            assert config == {'max_retries': 5, 'base_delay_seconds': 2.0}

            # Second call should use cache
            config2 = http_module._get_config()
            assert config2 == config
    finally:
        http_module._rate_limit_config = original
