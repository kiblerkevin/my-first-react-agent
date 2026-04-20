"""Tests for server/approval_server.py health endpoint."""

from unittest.mock import patch


@patch('server.approval_server.Memory')
def test_health_endpoint(mock_memory_cls):
    """Health endpoint returns 200 with status ok."""
    from server.approval_server import app

    with app.test_client() as client:
        response = client.get('/health')
        assert response.status_code == 200
        assert response.get_json() == {'status': 'ok'}
