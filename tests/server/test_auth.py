"""Tests for server/auth.py."""

from unittest.mock import patch

from server.auth import _resolve_role, get_current_user


class TestResolveRole:
    """Tests for role resolution from config."""

    @patch('server.auth._load_auth_config')
    def test_returns_mapped_role(self, mock_config):
        mock_config.return_value = {
            'role_mappings': {'admin@test.com': 'admin', 'editor@test.com': 'editor'}
        }
        assert _resolve_role('admin@test.com') == 'admin'
        assert _resolve_role('editor@test.com') == 'editor'

    @patch('server.auth._load_auth_config')
    def test_returns_anonymous_for_unknown(self, mock_config):
        mock_config.return_value = {'role_mappings': {}}
        assert _resolve_role('unknown@test.com') == 'anonymous'

    @patch('server.auth._load_auth_config')
    def test_handles_none_mappings(self, mock_config):
        mock_config.return_value = {'role_mappings': None}
        assert _resolve_role('anyone@test.com') == 'anonymous'


class TestRequireRole:
    """Tests for the require_role decorator."""

    @patch('server.approval_server.Memory')
    def test_unauthenticated_gets_401(self, mock_memory_cls):
        from server.approval_server import app

        with app.test_client() as client:
            response = client.get('/approve/some-token')
            assert response.status_code == 401
            assert b'Login Required' in response.data

    @patch('server.approval_server.Memory')
    def test_anonymous_user_gets_403(self, mock_memory_cls):
        from server.approval_server import app

        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user'] = {
                    'email': 'anon@test.com',
                    'name': 'Anon',
                    'picture': '',
                    'role': 'anonymous',
                }
            response = client.get('/approve/some-token')
            assert response.status_code == 403
            assert b'Access Denied' in response.data

    @patch('server.approval_server.Memory')
    def test_editor_can_access_approval_routes(self, mock_memory_cls):
        from server.approval_server import app

        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user'] = {
                    'email': 'editor@test.com',
                    'name': 'Editor',
                    'picture': '',
                    'role': 'editor',
                }
            # Tampered token returns 404 (passes auth, fails token validation)
            response = client.get('/approve/fake-token')
            assert response.status_code == 404

    @patch('server.approval_server.Memory')
    def test_admin_can_access_editor_routes(self, mock_memory_cls):
        from server.approval_server import app

        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user'] = {
                    'email': 'admin@test.com',
                    'name': 'Admin',
                    'picture': '',
                    'role': 'admin',
                }
            # Admin has higher privilege than editor
            response = client.get('/approve/fake-token')
            assert response.status_code == 404  # passes auth, fails token

    @patch('server.approval_server.Memory')
    def test_editor_cannot_access_admin_routes(self, mock_memory_cls):
        from server.approval_server import app

        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user'] = {
                    'email': 'editor@test.com',
                    'name': 'Editor',
                    'picture': '',
                    'role': 'editor',
                }
            response = client.get('/oauth/start')
            assert response.status_code == 403

    @patch('server.approval_server.Memory')
    def test_dashboard_accessible_without_auth(self, mock_memory_cls):
        from server.approval_server import app

        with app.test_client() as client:
            response = client.get('/dashboard')
            assert response.status_code == 200

    @patch('server.approval_server.Memory')
    def test_health_accessible_without_auth(self, mock_memory_cls):
        from server.approval_server import app

        with app.test_client() as client:
            response = client.get('/health')
            assert response.status_code == 200


class TestGetCurrentUser:
    """Tests for get_current_user."""

    @patch('server.approval_server.Memory')
    def test_returns_none_when_not_logged_in(self, mock_memory_cls):
        from server.approval_server import app

        with app.test_request_context():
            assert get_current_user() is None

    @patch('server.approval_server.Memory')
    def test_returns_user_from_session(self, mock_memory_cls):
        from flask import session

        from server.approval_server import app

        with app.test_request_context():
            app.secret_key = 'test'
            session['user'] = {'email': 'test@test.com', 'role': 'editor'}
            user = get_current_user()
            assert user['email'] == 'test@test.com'


class TestInitAuth:
    """Tests for init_auth."""

    @patch('server.auth.get_secret')
    @patch('server.auth._load_auth_config')
    def test_skips_when_not_configured(self, mock_config, mock_secret):
        from server.auth import init_auth

        mock_config.return_value = {'auth0': {'domain': ''}}
        mock_secret.return_value = None

        from flask import Flask

        test_app = Flask(__name__)
        test_app.secret_key = 'test'
        init_auth(test_app)  # Should not raise

    @patch('server.auth.OAuth')
    @patch('server.auth.get_secret')
    @patch('server.auth._load_auth_config')
    def test_registers_oauth_when_configured(
        self, mock_config, mock_secret, mock_oauth_cls
    ):
        from server.auth import init_auth

        mock_config.return_value = {
            'auth0': {
                'domain': 'test.auth0.com',
                'client_id_key': 'AUTH0_CLIENT_ID',
                'client_secret_key': 'AUTH0_CLIENT_SECRET',
            }
        }
        mock_secret.side_effect = lambda k: 'fake-id' if 'ID' in k else 'fake-secret'

        from flask import Flask

        test_app = Flask(__name__)
        test_app.secret_key = 'test'
        init_auth(test_app)

        mock_oauth_cls.return_value.register.assert_called_once()
