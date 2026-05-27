"""Mixin for database backup and log retention operations."""

import os
import sqlite3
from datetime import datetime, timedelta

from utils.logger.logger import setup_logger

logger = setup_logger(__name__)


class BackupMixin:
    """Database backup, log purge, and retention operations."""

    def backup_database(self) -> str | None:
        """Create a timestamped backup of the SQLite database using the backup API.

        Returns:
            Path to the backup file, or None on failure.
        """
        os.makedirs(self.backup_path, exist_ok=True)
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        backup_file = os.path.join(self.backup_path, f'articles_{timestamp}.db')

        try:
            source = sqlite3.connect(self.db_path)
            dest = sqlite3.connect(backup_file)
            source.backup(dest)
            dest.close()
            source.close()
            os.chmod(backup_file, 0o600)
            logger.info(f'Database backup created: {backup_file}')
            return backup_file
        except Exception as e:
            logger.error(f'Database backup failed: {e}')
            return None

    def purge_old_backups(self) -> None:
        """Delete backup files older than the configured retention period."""
        if not os.path.exists(self.backup_path):
            return

        cutoff = datetime.utcnow() - timedelta(days=self.backup_retention_days)
        count = 0
        for filename in os.listdir(self.backup_path):
            filepath = os.path.join(self.backup_path, filename)
            if not os.path.isfile(filepath):
                continue
            modified = datetime.utcfromtimestamp(os.path.getmtime(filepath))
            if modified < cutoff:
                os.remove(filepath)
                count += 1
        if count:
            logger.info(
                f'Purged {count} backup(s) older than {self.backup_retention_days} days.'
            )

    def purge_old_logs(self) -> None:
        """Purge log files older than the retention period."""
        cutoff = datetime.utcnow() - timedelta(days=self.log_retention_days)
        log_dir = 'logs'
        if not os.path.exists(log_dir):
            return
        count = 0
        for filename in os.listdir(log_dir):
            filepath = os.path.join(log_dir, filename)
            if not os.path.isfile(filepath):
                continue
            modified = datetime.utcfromtimestamp(os.path.getmtime(filepath))
            if modified < cutoff:
                os.remove(filepath)
                count += 1
        if count:
            logger.info(
                f'Purged {count} log file(s) older than {self.log_retention_days} days.'
            )
