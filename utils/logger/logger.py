"""Structured logging with JSON file output, console output, and run_id context."""

import json
import logging
import os
import threading
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Any

# Thread-local storage for correlation context
_log_context = threading.local()

# Project module prefixes that get the configured default level
_PROJECT_PREFIXES = (
    'agent',
    'tools',
    'utils',
    'memory',
    'workflow',
    'server',
    'constants',
    'models',
)

# Default config used before yaml is loaded (avoids circular imports)
_DEFAULT_CONFIG: dict[str, Any] = {
    'retention_days': 14,
    'max_file_bytes': 10_485_760,
    'backup_count': 5,
    'default_level': 'INFO',
    'third_party_level': 'WARNING',
}

_config_loaded = False
_logging_config: dict[str, Any] = dict(_DEFAULT_CONFIG)


def _load_config() -> dict[str, Any]:
    """Load logging config from database.yaml, cached after first call."""
    global _config_loaded, _logging_config
    if _config_loaded:
        return _logging_config
    try:
        import yaml

        with open('config/database.yaml', 'r') as f:
            config = yaml.safe_load(f)
        _logging_config = config.get('logging', _DEFAULT_CONFIG)
    except Exception:
        _logging_config = dict(_DEFAULT_CONFIG)
    _config_loaded = True
    return _logging_config


def set_log_context(**kwargs: Any) -> None:
    """Set thread-local context fields that appear in every log line.

    Args:
        **kwargs: Key-value pairs to inject (e.g. run_id='abc').
    """
    for key, value in kwargs.items():
        setattr(_log_context, key, value)


def clear_log_context() -> None:
    """Clear all thread-local context fields."""
    _log_context.__dict__.clear()


class _ContextFilter(logging.Filter):
    """Injects thread-local context fields into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add context fields to the record."""
        record.run_id = getattr(_log_context, 'run_id', None)  # type: ignore[attr-defined]
        return True


class _JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as JSON."""
        entry: dict[str, Any] = {
            'timestamp': datetime.utcfromtimestamp(record.created).isoformat() + 'Z',
            'level': record.levelname,
            'module': record.name,
            'function': record.funcName,
            'line': record.lineno,
            'message': record.getMessage(),
            'run_id': getattr(record, 'run_id', None),
        }
        if record.exc_info and record.exc_info[1]:
            entry['exception'] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


class _ConsoleFormatter(logging.Formatter):
    """Human-readable console format with optional run_id suffix."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record for console output."""
        run_id = getattr(record, 'run_id', None)
        suffix = f' [run_id={run_id}]' if run_id else ''
        timestamp = datetime.utcfromtimestamp(record.created).strftime(
            '%Y-%m-%d %H:%M:%S'
        )
        return (
            f'{timestamp} - {record.name} - {record.levelname} - '
            f'{record.getMessage()}{suffix}'
        )


def setup_logger(
    name: str = 'chicago_sports', log_level: str | None = None
) -> logging.Logger:
    """Set up a logger with JSON file and human-readable console handlers.

    Args:
        name: Logger name, typically __name__ of the calling module.
        log_level: Override log level. Defaults to config or LOG_LEVEL env var.

    Returns:
        Configured logger instance.
    """
    config = _load_config()

    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    # Determine level: explicit override > env var > config-based default
    is_project = any(name.startswith(p) for p in _PROJECT_PREFIXES)
    if log_level is not None:
        effective_level = log_level
    elif is_project:
        effective_level = os.getenv('LOG_LEVEL', config.get('default_level', 'INFO'))
    else:
        effective_level = config.get('third_party_level', 'WARNING')
    logger.setLevel(getattr(logging, effective_level.upper()))

    # Context filter for run_id injection
    context_filter = _ContextFilter()

    # Console handler — human-readable
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(_ConsoleFormatter())
    console_handler.addFilter(context_filter)

    # File handler — JSON, rotating
    os.makedirs('logs', exist_ok=True)
    log_file = f'logs/app_{datetime.now().strftime("%Y%m%d")}.log'
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=config.get('max_file_bytes', 10_485_760),
        backupCount=config.get('backup_count', 5),
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(_JsonFormatter())
    file_handler.addFilter(context_filter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
