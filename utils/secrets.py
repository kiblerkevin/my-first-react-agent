"""Pluggable secrets management with macOS Keychain and env var providers."""

import os
import subprocess
from abc import ABC, abstractmethod
from typing import Any

_provider_instance: 'SecretsProvider | None' = None
_config_loaded = False
_secrets_config: dict[str, Any] = {}

DATABASE_CONFIG_PATH = 'config/database.yaml'


class SecretsProvider(ABC):
    """Abstract base for secrets providers."""

    @abstractmethod
    def get(self, key: str) -> str | None:
        """Retrieve a secret by key.

        Args:
            key: The secret key name.

        Returns:
            The secret value, or None if not found.
        """

    @abstractmethod
    def set(self, key: str, value: str) -> None:
        """Store a secret.

        Args:
            key: The secret key name.
            value: The secret value.
        """


class EnvProvider(SecretsProvider):
    """Reads secrets from environment variables."""

    def get(self, key: str) -> str | None:
        """Retrieve a secret from environment variables.

        Args:
            key: The environment variable name.

        Returns:
            The value, or None if not set.
        """
        return os.environ.get(key)

    def set(self, key: str, value: str) -> None:
        """Set a secret as an environment variable (current process only).

        Args:
            key: The environment variable name.
            value: The value to set.
        """
        os.environ[key] = value


class KeychainProvider(SecretsProvider):
    """Reads/writes secrets via macOS Keychain using the security CLI."""

    def __init__(self, service: str = 'chicago-sports-recap') -> None:
        """Initialize with a Keychain service name.

        Args:
            service: The Keychain service name to store secrets under.
        """
        self.service = service
        self._env_fallback = EnvProvider()

    def get(self, key: str) -> str | None:
        """Retrieve a secret from macOS Keychain, falling back to env.

        Args:
            key: The secret key name (used as the Keychain account).

        Returns:
            The secret value, or None if not found.
        """
        try:
            result = subprocess.run(
                [
                    'security',
                    'find-generic-password',
                    '-s',
                    self.service,
                    '-a',
                    key,
                    '-w',
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return self._env_fallback.get(key)

    def set(self, key: str, value: str) -> None:
        """Store a secret in macOS Keychain.

        Args:
            key: The secret key name (used as the Keychain account).
            value: The secret value.
        """
        # Delete existing entry if present (security CLI errors on duplicates)
        subprocess.run(
            ['security', 'delete-generic-password', '-s', self.service, '-a', key],
            capture_output=True,
        )
        subprocess.run(
            [
                'security',
                'add-generic-password',
                '-s',
                self.service,
                '-a',
                key,
                '-w',
                value,
            ],
            capture_output=True,
            check=True,
        )


def _load_secrets_config() -> dict[str, Any]:
    """Load secrets config from database.yaml, cached after first call."""
    global _config_loaded, _secrets_config
    if _config_loaded:
        return _secrets_config
    try:
        import yaml

        with open(DATABASE_CONFIG_PATH, 'r') as f:
            config = yaml.safe_load(f)
        _secrets_config = config.get('secrets', {})
    except Exception:
        _secrets_config = {}
    _config_loaded = True
    return _secrets_config


def get_provider() -> SecretsProvider:
    """Get the singleton secrets provider based on config.

    Returns:
        The configured SecretsProvider instance.
    """
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance

    # Check env var override first, then config file
    provider_name = os.environ.get('SECRETS_PROVIDER')
    if not provider_name:
        config = _load_secrets_config()
        provider_name = config.get('provider', 'env')

    if provider_name == 'keychain':
        config = _load_secrets_config()
        service = config.get('keychain_service', 'chicago-sports-recap')
        _provider_instance = KeychainProvider(service=service)
    else:
        _provider_instance = EnvProvider()

    return _provider_instance


def set_provider(provider: SecretsProvider) -> None:
    """Override the singleton provider (for testing).

    Args:
        provider: The provider instance to use.
    """
    global _provider_instance
    _provider_instance = provider


def get_secret(key: str) -> str | None:
    """Retrieve a secret from the configured provider.

    Args:
        key: The secret key name.

    Returns:
        The secret value, or None if not found.
    """
    return get_provider().get(key)
