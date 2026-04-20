"""Tests for utils/logger/logger.py."""

import json
import logging
from unittest.mock import MagicMock, patch

from utils.logger.logger import (
    _ConsoleFormatter,
    _ContextFilter,
    _JsonFormatter,
    _load_config,
    clear_log_context,
    set_log_context,
    setup_logger,
)


class TestLogContext:
    """Tests for thread-local log context."""

    def test_set_and_clear_context(self):
        set_log_context(run_id='test-123')
        from utils.logger.logger import _log_context

        assert _log_context.run_id == 'test-123'
        clear_log_context()
        assert not hasattr(_log_context, 'run_id')

    def test_set_multiple_fields(self):
        set_log_context(run_id='abc', step='fetch')
        from utils.logger.logger import _log_context

        assert _log_context.run_id == 'abc'
        assert _log_context.step == 'fetch'
        clear_log_context()


class TestContextFilter:
    """Tests for the _ContextFilter."""

    def test_injects_run_id_into_record(self):
        set_log_context(run_id='filter-test')
        f = _ContextFilter()
        record = logging.LogRecord('test', logging.INFO, '', 0, 'msg', (), None)
        result = f.filter(record)
        assert result is True
        assert record.run_id == 'filter-test'  # type: ignore[attr-defined]
        clear_log_context()

    def test_injects_none_when_no_context(self):
        clear_log_context()
        f = _ContextFilter()
        record = logging.LogRecord('test', logging.INFO, '', 0, 'msg', (), None)
        f.filter(record)
        assert record.run_id is None  # type: ignore[attr-defined]


class TestJsonFormatter:
    """Tests for the _JsonFormatter."""

    def test_formats_as_json(self):
        formatter = _JsonFormatter()
        record = logging.LogRecord('mymodule', logging.WARNING, 'file.py', 42, 'test message', (), None)
        record.run_id = 'json-test'  # type: ignore[attr-defined]
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed['level'] == 'WARNING'
        assert parsed['module'] == 'mymodule'
        assert parsed['message'] == 'test message'
        assert parsed['run_id'] == 'json-test'
        assert parsed['line'] == 42
        assert 'timestamp' in parsed

    def test_includes_exception_info(self):
        formatter = _JsonFormatter()
        try:
            raise ValueError('boom')
        except ValueError:
            import sys
            record = logging.LogRecord('mod', logging.ERROR, '', 0, 'err', (), sys.exc_info())
            record.run_id = None  # type: ignore[attr-defined]
            output = formatter.format(record)
            parsed = json.loads(output)
            assert 'exception' in parsed
            assert 'boom' in parsed['exception']


class TestConsoleFormatter:
    """Tests for the _ConsoleFormatter."""

    def test_human_readable_format(self):
        formatter = _ConsoleFormatter()
        record = logging.LogRecord('mymod', logging.INFO, '', 0, 'hello', (), None)
        record.run_id = None  # type: ignore[attr-defined]
        output = formatter.format(record)
        assert 'mymod' in output
        assert 'INFO' in output
        assert 'hello' in output
        assert 'run_id' not in output

    def test_includes_run_id_when_set(self):
        formatter = _ConsoleFormatter()
        record = logging.LogRecord('mymod', logging.INFO, '', 0, 'hello', (), None)
        record.run_id = 'console-test'  # type: ignore[attr-defined]
        output = formatter.format(record)
        assert '[run_id=console-test]' in output


class TestSetupLogger:
    """Tests for setup_logger."""

    def test_returns_existing_logger_with_handlers(self):
        logger1 = setup_logger('test_reuse_logger')
        count = len(logger1.handlers)
        assert count > 0
        logger2 = setup_logger('test_reuse_logger')
        assert logger2 is logger1
        assert len(logger2.handlers) == count
        logger1.handlers.clear()

    def test_project_module_gets_default_level(self):
        logger = setup_logger('agent.test_module')
        # Should use the configured default level, not WARNING
        assert logger.level <= logging.INFO
        logger.handlers.clear()

    def test_third_party_module_gets_warning_level(self):
        name = 'xyzlib_unique_third_party_test'
        # Ensure clean state
        logging.getLogger(name).handlers.clear()
        logger = setup_logger(name)
        assert logger.level >= logging.WARNING
        logger.handlers.clear()

    def test_respects_log_level_override(self):
        logger = setup_logger('test_override_level', log_level='DEBUG')
        assert logger.level == logging.DEBUG
        logger.handlers.clear()

    def test_has_console_and_file_handlers(self):
        logger = setup_logger('test_handlers_check')
        handler_types = [type(h).__name__ for h in logger.handlers]
        assert 'StreamHandler' in handler_types
        assert 'RotatingFileHandler' in handler_types
        logger.handlers.clear()


class TestLoadConfig:
    """Tests for _load_config."""

    def test_loads_from_yaml(self):
        import utils.logger.logger as logger_module

        original_loaded = logger_module._config_loaded
        original_config = logger_module._logging_config
        logger_module._config_loaded = False

        try:
            with patch('builtins.open'), \
                 patch('yaml.safe_load', return_value={'logging': {'retention_days': 7, 'default_level': 'DEBUG'}}):
                config = _load_config()
                assert config['retention_days'] == 7
                assert config['default_level'] == 'DEBUG'
        finally:
            logger_module._config_loaded = original_loaded
            logger_module._logging_config = original_config

    def test_uses_defaults_on_file_error(self):
        import utils.logger.logger as logger_module

        original_loaded = logger_module._config_loaded
        original_config = logger_module._logging_config
        logger_module._config_loaded = False

        try:
            with patch('builtins.open', side_effect=FileNotFoundError):
                config = _load_config()
                assert config['retention_days'] == 14
                assert config['default_level'] == 'INFO'
        finally:
            logger_module._config_loaded = original_loaded
            logger_module._logging_config = original_config

    def test_caches_after_first_load(self):
        import utils.logger.logger as logger_module

        original_loaded = logger_module._config_loaded
        original_config = logger_module._logging_config
        logger_module._config_loaded = False

        try:
            with patch('builtins.open'), \
                 patch('yaml.safe_load', return_value={'logging': {'retention_days': 99}}) as mock_yaml:
                _load_config()
                _load_config()
                # yaml.safe_load should only be called once
                mock_yaml.assert_called_once()
        finally:
            logger_module._config_loaded = original_loaded
            logger_module._logging_config = original_config
