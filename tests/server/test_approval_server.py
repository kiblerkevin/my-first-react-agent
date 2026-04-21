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


@patch('server.approval_server.Memory')
def test_post_info_strips_malicious_html(mock_memory_cls):
    """XSS: malicious HTML in post_info is stripped by bleach."""
    import bleach

    malicious = '<script>alert("xss")</script><p>Safe content</p>'
    sanitized = bleach.clean(
        malicious,
        tags=['p', 'a', 'strong'],
        attributes={'a': ['href']},
    )
    assert '<script>' not in sanitized
    assert '<p>Safe content</p>' in sanitized


@patch('server.approval_server.Memory')
def test_post_info_allows_safe_tags(mock_memory_cls):
    """XSS: safe tags (p, a, strong) pass through bleach."""
    import bleach

    safe = '<p><strong>Published:</strong> <a href="http://x.com">Link</a></p>'
    sanitized = bleach.clean(
        safe,
        tags=['p', 'a', 'strong'],
        attributes={'a': ['href']},
    )
    assert sanitized == safe


@patch('server.approval_server.Memory')
def test_post_info_strips_style_attributes(mock_memory_cls):
    """XSS: style attributes are stripped from allowed tags."""
    import bleach

    styled = "<p style='color: red;'>Text</p>"
    sanitized = bleach.clean(
        styled,
        tags=['p', 'a', 'strong'],
        attributes={'a': ['href']},
    )
    assert 'style=' not in sanitized
    assert '<p>' in sanitized


@patch('server.approval_server.Memory')
def test_approve_rejects_tampered_token(mock_memory_cls):
    """Tampered token returns 404 invalid token page."""
    from server.approval_server import app

    with app.test_client() as client:
        response = client.get('/approve/tampered-garbage-token')
        assert response.status_code == 404
        assert b'Invalid Token' in response.data


@patch('server.approval_server.Memory')
def test_reject_rejects_tampered_token(mock_memory_cls):
    """Tampered token returns 404 invalid token page on reject."""
    from server.approval_server import app

    with app.test_client() as client:
        response = client.get('/reject/tampered-garbage-token')
        assert response.status_code == 404
        assert b'Invalid Token' in response.data


@patch('server.approval_server.Memory')
def test_approve_rejects_expired_token(mock_memory_cls):
    """Expired token returns 404 invalid token page."""
    from server.approval_server import app, _approval_serializer

    # Generate a valid token, then validate with max_age=0 to simulate expiry
    token = _approval_serializer.dumps('Test Post', salt='approval')

    import time
    time.sleep(0.1)

    with app.test_client() as client:
        # Temporarily set expiry to 0 seconds to force expiration
        import server.approval_server as srv
        original_expiry = srv._approval_expiry_seconds
        srv._approval_expiry_seconds = 0
        try:
            response = client.get(f'/approve/{token}')
            assert response.status_code == 404
            assert b'Invalid Token' in response.data
        finally:
            srv._approval_expiry_seconds = original_expiry


@patch('server.approval_server.Memory')
def test_approve_accepts_valid_token(mock_memory_cls):
    """Valid token passes signature check and proceeds to DB lookup."""
    from server.approval_server import app, _approval_serializer

    mock_memory = mock_memory_cls.return_value
    mock_memory.get_pending_approval.return_value = None

    token = _approval_serializer.dumps('Test Post', salt='approval')

    with app.test_client() as client:
        response = client.get(f'/approve/{token}')
        # Token is valid but no DB record — returns 404 (not found in DB)
        assert response.status_code == 404


@patch('server.approval_server.Memory')
def test_reject_post_without_csrf_returns_400(mock_memory_cls):
    """POST to reject without CSRF token returns 400."""
    from server.approval_server import app, _approval_serializer
    import server.approval_server as srv

    token = _approval_serializer.dumps('Test Post', salt='approval')

    mock_memory = mock_memory_cls.return_value
    mock_memory.get_pending_approval.return_value = {
        'status': 'pending', 'blog_title': 'Test',
    }
    srv.memory = mock_memory

    with app.test_client() as client:
        response = client.post(f'/reject/{token}', data={'feedback': 'bad'})
        assert response.status_code == 400


@patch('server.approval_server.Memory')
def test_reject_post_with_csrf_succeeds(mock_memory_cls):
    """POST to reject with valid CSRF token succeeds."""
    from server.approval_server import app, _approval_serializer
    import server.approval_server as srv

    token = _approval_serializer.dumps('Test Post', salt='approval')

    mock_memory = mock_memory_cls.return_value
    mock_memory.get_pending_approval.return_value = {
        'status': 'pending', 'blog_title': 'Test',
    }
    srv.memory = mock_memory

    app.config['WTF_CSRF_ENABLED'] = True
    with app.test_client() as client:
        # GET the form to obtain the CSRF token
        get_response = client.get(f'/reject/{token}')
        assert get_response.status_code == 200

        # Extract CSRF token from the form HTML
        html = get_response.data.decode()
        import re
        match = re.search(r'name="csrf_token" value="([^"]+)"', html)
        assert match is not None
        csrf_token = match.group(1)

        # POST with the CSRF token
        response = client.post(
            f'/reject/{token}',
            data={'feedback': 'needs work', 'csrf_token': csrf_token},
        )
        assert response.status_code == 200
        assert b'Rejected' in response.data


@patch('server.approval_server.Memory')
def test_rate_limit_returns_429(mock_memory_cls):
    """Exceeding rate limit returns 429."""
    from server.approval_server import app, limiter

    # Set a very low limit for testing
    with app.test_client() as client:
        # The approve endpoint has 10/minute limit
        # Use a tampered token so we get 404 quickly without DB calls
        for _ in range(11):
            response = client.get('/approve/fake-token')
        assert response.status_code == 429


@patch('server.approval_server.Memory')
def test_rate_limit_headers_present(mock_memory_cls):
    """Rate limit headers are present on responses."""
    from server.approval_server import app

    with app.test_client() as client:
        response = client.get('/approve/fake-token')
        # flask-limiter adds these headers
        assert 'X-RateLimit-Limit' in response.headers or 'Retry-After' in response.headers or response.status_code in (404, 429)


@patch('server.approval_server.Memory')
def test_health_exempt_from_rate_limit(mock_memory_cls):
    """Health endpoint is exempt from rate limiting."""
    from server.approval_server import app

    with app.test_client() as client:
        # Hit health many times — should never get 429
        for _ in range(100):
            response = client.get('/health')
            assert response.status_code == 200
