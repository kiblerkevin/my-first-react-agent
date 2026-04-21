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
