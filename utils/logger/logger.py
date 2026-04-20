"""Logging configuration with file and console handlers."""

import logging
import os
from datetime import datetime


def setup_logger(
    name: str = 'chicago_sports', log_level: str | None = None
) -> logging.Logger:
    """Set up a logger with file and console handlers.

    Args:
        name: Logger name, typically __name__ of the calling module.
        log_level: Override log level. Defaults to LOG_LEVEL env var or INFO.

    Returns:
        Configured logger instance.
    """
    if log_level is None:
        log_level = os.getenv('LOG_LEVEL', 'INFO')

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper()))

    if logger.handlers:
        return logger

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_format)

    # File handler
    os.makedirs('logs', exist_ok=True)
    log_file = f'logs/app_{datetime.now().strftime("%Y%m%d")}.log'
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    file_handler.setFormatter(file_format)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
