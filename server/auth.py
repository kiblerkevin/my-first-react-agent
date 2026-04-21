"""Auth0 integration with role-based access control."""

from functools import wraps
from typing import Any

import yaml
from authlib.integrations.flask_client import OAuth
from flask import Flask, redirect, render_template_string, session, url_for

from utils.logger.logger import setup_logger
from utils.secrets import get_secret

logger = setup_logger(__name__)

AUTH_CONFIG_PATH = 'config/auth.yaml'

_auth_config: dict[str, Any] = {}
_oauth: OAuth | None = None

LOGIN_REQUIRED_PAGE = """
<html><body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
<h1 style="color: #6c757d;">🔒 Login Required</h1>
<p>You need to log in to access this page.</p>
<a href="{{ login_url }}"
   style="background-color: #007bff; color: white; padding: 12px 30px;
          text-decoration: none; border-radius: 5px; font-size: 16px;
          display: inline-block; margin-top: 15px;">
    Log in with Auth0
</a>
</body></html>
"""

FORBIDDEN_PAGE = """
<html><body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
<h1 style="color: #dc3545;">⛔ Access Denied</h1>
<p>You don't have permission to access this page.</p>
<p>Logged in as: <strong>{{ email }}</strong> (role: {{ role }})</p>
<a href="{{ logout_url }}" style="color: #666; font-size: 14px;">Log out</a>
</body></html>
"""


def _load_auth_config() -> dict[str, Any]:
    """Load auth config from auth.yaml, cached after first call."""
    global _auth_config
    if _auth_config:
        return _auth_config
    try:
        with open(AUTH_CONFIG_PATH, 'r') as f:
            _auth_config = yaml.safe_load(f) or {}
    except Exception:
        _auth_config = {}
    return _auth_config


def init_auth(app: Flask) -> None:
    """Initialize Auth0 OAuth on the Flask app.

    Args:
        app: The Flask application instance.
    """
    global _oauth
    config = _load_auth_config()
    auth0_config = config.get('auth0', {})

    domain = auth0_config.get('domain', '')
    client_id = get_secret(auth0_config.get('client_id_key', 'AUTH0_CLIENT_ID'))
    client_secret = get_secret(
        auth0_config.get('client_secret_key', 'AUTH0_CLIENT_SECRET')
    )

    if not domain or not client_id or not client_secret:
        logger.warning(
            'Auth0 not configured — authentication disabled. '
            'Set auth0.domain, AUTH0_CLIENT_ID, and AUTH0_CLIENT_SECRET.'
        )
        return

    _oauth = OAuth(app)
    _oauth.register(
        'auth0',
        client_id=client_id,
        client_secret=client_secret,
        server_metadata_url=f'https://{domain}/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'},
    )

    @app.route('/auth/login')
    def auth_login() -> Any:
        """Redirect to Auth0 login page."""
        callback_url = url_for('auth_callback', _external=True)
        return _oauth.auth0.authorize_redirect(callback_url)

    @app.route('/auth/callback')
    def auth_callback() -> Any:
        """Handle Auth0 callback and establish session."""
        token = _oauth.auth0.authorize_access_token()
        userinfo = token.get('userinfo', {})
        session['user'] = {
            'email': userinfo.get('email', ''),
            'name': userinfo.get('name', ''),
            'picture': userinfo.get('picture', ''),
            'role': _resolve_role(userinfo.get('email', '')),
        }
        logger.info(
            f'Auth0 login: {session["user"]["email"]} (role: {session["user"]["role"]})'
        )
        return redirect(session.pop('auth_next', '/dashboard'))

    @app.route('/auth/logout')
    def auth_logout() -> Any:
        """Clear session and redirect to Auth0 logout."""
        session.clear()
        return redirect(
            f'https://{domain}/v2/logout?returnTo={url_for("health", _external=True)}'
        )

    logger.info(f'Auth0 initialized for domain: {domain}')


def _resolve_role(email: str) -> str:
    """Resolve a user's role from the config mapping.

    Args:
        email: The user's email address.

    Returns:
        Role string: 'admin', 'editor', or 'anonymous'.
    """
    config = _load_auth_config()
    mappings = config.get('role_mappings') or {}
    return mappings.get(email, 'anonymous')


def get_current_user() -> dict[str, Any] | None:
    """Get the current authenticated user from the session.

    Returns:
        User dict with email, name, picture, role — or None if not logged in.
    """
    return session.get('user')


def require_role(role: str):
    """Restrict route access to users with the specified role or higher.

    Role hierarchy: admin > editor > anonymous.
    Anonymous users are redirected to login.
    Authenticated users with insufficient role see a 403 page.

    Args:
        role: Minimum required role ('editor' or 'admin').
    """
    role_hierarchy = {'anonymous': 0, 'editor': 1, 'admin': 2}

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()

            if not user:
                # Not logged in — redirect to login
                try:
                    login_url = url_for('auth_login')
                except Exception:
                    login_url = '/auth/login'
                return (
                    render_template_string(
                        LOGIN_REQUIRED_PAGE,
                        login_url=login_url,
                    ),
                    401,
                )

            user_role = user.get('role', 'anonymous')
            required_level = role_hierarchy.get(role, 0)
            user_level = role_hierarchy.get(user_role, 0)

            if user_level < required_level:
                try:
                    logout_url = url_for('auth_logout')
                except Exception:
                    logout_url = '/auth/logout'
                return (
                    render_template_string(
                        FORBIDDEN_PAGE,
                        email=user.get('email', ''),
                        role=user_role,
                        logout_url=logout_url,
                    ),
                    403,
                )

            return f(*args, **kwargs)

        return decorated_function

    return decorator
