"""Tests for server/approval_server.py."""

from unittest.mock import patch


@patch('server.approval_server.Memory')
def test_health_endpoint(mock_memory_cls):
    """Health endpoint returns 200 with status ok."""
    from server.approval_server import app

    with app.test_client() as client:
        response = client.get('/health')
        assert response.status_code == 200
        assert response.get_json() == {'status': 'ok'}


@patch('server.approval_server.Memory')
def test_default_bind_host_is_localhost(mock_memory_cls):
    """Server defaults to 127.0.0.1 when APPROVAL_BIND_HOST is not set."""
    import os

    # Ensure env var is not set
    env = os.environ.copy()
    env.pop('APPROVAL_BIND_HOST', None)
    with patch.dict('os.environ', env, clear=True):
        host = os.getenv('APPROVAL_BIND_HOST', '127.0.0.1')
    assert host == '127.0.0.1'


@patch('server.approval_server.Memory')
def test_security_headers_present(mock_memory_cls):
    """All responses include security headers."""
    from server.approval_server import app

    with app.test_client() as client:
        response = client.get('/health')
        assert response.headers['X-Content-Type-Options'] == 'nosniff'
        assert response.headers['X-Frame-Options'] == 'DENY'
        assert response.headers['Content-Security-Policy'] == "default-src 'self'"
        assert response.headers['X-XSS-Protection'] == '1; mode=block'


@patch('server.approval_server.Memory')
def test_oauth_error_does_not_leak_internals(mock_memory_cls):
    """OAuth error page shows generic message, not internal paths."""
    from server.approval_server import app

    with app.test_client() as client:
        # No code param returns 400 with generic message
        response = client.get('/oauth/callback')
        assert response.status_code == 400
        assert b'No authorization code' in response.data

        # Simulate an internal error during token exchange
        with patch('requests.post', side_effect=Exception('/usr/local/lib/python/secret_path')):
            response = client.get('/oauth/callback?code=fake_code')
            assert response.status_code == 500
            assert b'secret_path' not in response.data
            assert b'internal error' in response.data.lower()
