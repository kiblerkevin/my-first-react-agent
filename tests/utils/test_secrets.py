"""Tests for utils/secrets.py."""

import os
from unittest.mock import MagicMock, patch

import utils.secrets as secrets_module
from utils.secrets import (
    EnvProvider,
    KeychainProvider,
    SecretsProvider,
    get_provider,
    get_secret,
    set_provider,
)


class TestEnvProvider:
    """Tests for EnvProvider."""

    def test_get_returns_env_var(self):
        provider = EnvProvider()
        with patch.dict('os.environ', {'TEST_KEY': 'test_value'}):
            assert provider.get('TEST_KEY') == 'test_value'

    def test_get_returns_none_when_missing(self):
        provider = EnvProvider()
        with patch.dict('os.environ', {}, clear=True):
            assert provider.get('NONEXISTENT') is None

    def test_set_stores_in_environ(self):
        provider = EnvProvider()
        provider.set('NEW_KEY', 'new_value')
        assert os.environ.get('NEW_KEY') == 'new_value'
        del os.environ['NEW_KEY']


class TestKeychainProvider:
    """Tests for KeychainProvider."""

    @patch('utils.secrets.subprocess.run')
    def test_get_returns_keychain_value(self, mock_run):
        mock_run.return_value = MagicMock(stdout='secret_value\n', returncode=0)
        provider = KeychainProvider(service='test-service')
        result = provider.get('MY_KEY')
        assert result == 'secret_value'
        mock_run.assert_called_once_with(
            [
                'security',
                'find-generic-password',
                '-s',
                'test-service',
                '-a',
                'MY_KEY',
                '-w',
            ],
            capture_output=True,
            text=True,
            check=True,
        )

    @patch('utils.secrets.subprocess.run')
    def test_get_falls_back_to_env(self, mock_run):
        from subprocess import CalledProcessError

        mock_run.side_effect = CalledProcessError(1, 'security')
        provider = KeychainProvider()
        with patch.dict('os.environ', {'FALLBACK_KEY': 'env_value'}):
            assert provider.get('FALLBACK_KEY') == 'env_value'

    @patch('utils.secrets.subprocess.run')
    def test_get_falls_back_on_file_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        provider = KeychainProvider()
        with patch.dict('os.environ', {'KEY': 'val'}):
            assert provider.get('KEY') == 'val'

    @patch('utils.secrets.subprocess.run')
    def test_set_deletes_then_adds(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        provider = KeychainProvider(service='test-svc')
        provider.set('KEY', 'VALUE')
        assert mock_run.call_count == 2
        # First call: delete
        assert mock_run.call_args_list[0][0][0][0] == 'security'
        assert 'delete-generic-password' in mock_run.call_args_list[0][0][0]
        # Second call: add
        assert 'add-generic-password' in mock_run.call_args_list[1][0][0]


class TestGetProvider:
    """Tests for get_provider factory."""

    def setup_method(self):
        secrets_module._provider_instance = None
        secrets_module._config_loaded = False

    def teardown_method(self):
        secrets_module._provider_instance = None
        secrets_module._config_loaded = False

    def test_returns_env_provider_by_default(self):
        with patch.dict('os.environ', {}, clear=False):
            os.environ.pop('SECRETS_PROVIDER', None)
            with (
                patch('builtins.open'),
                patch('yaml.safe_load', return_value={'secrets': {'provider': 'env'}}),
            ):
                provider = get_provider()
                assert isinstance(provider, EnvProvider)

    def test_returns_keychain_provider_when_configured(self):
        with patch.dict('os.environ', {}, clear=False):
            os.environ.pop('SECRETS_PROVIDER', None)
            with (
                patch('builtins.open'),
                patch(
                    'yaml.safe_load',
                    return_value={
                        'secrets': {'provider': 'keychain', 'keychain_service': 'test'}
                    },
                ),
            ):
                provider = get_provider()
                assert isinstance(provider, KeychainProvider)
                assert provider.service == 'test'

    def test_env_var_overrides_config(self):
        with (
            patch.dict('os.environ', {'SECRETS_PROVIDER': 'env'}),
            patch('builtins.open'),
            patch('yaml.safe_load', return_value={'secrets': {'provider': 'keychain'}}),
        ):
            provider = get_provider()
            assert isinstance(provider, EnvProvider)

    def test_returns_singleton(self):
        with patch.dict('os.environ', {}, clear=False):
            os.environ.pop('SECRETS_PROVIDER', None)
            with (
                patch('builtins.open'),
                patch('yaml.safe_load', return_value={'secrets': {'provider': 'env'}}),
            ):
                p1 = get_provider()
                p2 = get_provider()
                assert p1 is p2


class TestSetProvider:
    """Tests for set_provider injection."""

    def teardown_method(self):
        secrets_module._provider_instance = None

    def test_overrides_provider(self):
        mock = MagicMock(spec=SecretsProvider)
        mock.get.return_value = 'injected'
        set_provider(mock)
        assert get_secret('ANY_KEY') == 'injected'


class TestGetSecret:
    """Tests for the get_secret convenience function."""

    def teardown_method(self):
        secrets_module._provider_instance = None

    def test_delegates_to_provider(self):
        mock = MagicMock(spec=SecretsProvider)
        mock.get.return_value = 'value123'
        set_provider(mock)
        assert get_secret('KEY') == 'value123'
        mock.get.assert_called_once_with('KEY')


class TestLoadSecretsConfig:
    """Tests for _load_secrets_config."""

    def setup_method(self):
        secrets_module._config_loaded = False
        secrets_module._secrets_config = {}

    def teardown_method(self):
        secrets_module._config_loaded = False
        secrets_module._secrets_config = {}

    def test_loads_from_yaml(self):
        with (
            patch('builtins.open'),
            patch(
                'yaml.safe_load',
                return_value={
                    'secrets': {'provider': 'keychain', 'keychain_service': 'test'}
                },
            ),
        ):
            config = secrets_module._load_secrets_config()
            assert config['provider'] == 'keychain'

    def test_returns_empty_on_error(self):
        with patch('builtins.open', side_effect=FileNotFoundError):
            config = secrets_module._load_secrets_config()
            assert config == {}

    def test_caches_after_first_load(self):
        with (
            patch('builtins.open'),
            patch(
                'yaml.safe_load', return_value={'secrets': {'provider': 'env'}}
            ) as mock_yaml,
        ):
            secrets_module._load_secrets_config()
            secrets_module._load_secrets_config()
            mock_yaml.assert_called_once()
