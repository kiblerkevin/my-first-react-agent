"""Tests for utils/logger/logger.py."""

import logging

from utils.logger.logger import setup_logger


def test_returns_existing_logger_with_handlers():
    """Line 27: returns early when logger already has handlers."""
    # First call sets up handlers
    logger1 = setup_logger('test_logger_reuse')
    handler_count = len(logger1.handlers)
    assert handler_count > 0

    # Second call should return same logger without adding more handlers
    logger2 = setup_logger('test_logger_reuse')
    assert logger2 is logger1
    assert len(logger2.handlers) == handler_count

    # Cleanup
    logger1.handlers.clear()
