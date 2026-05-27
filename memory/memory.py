"""Unified memory facade composing domain-specific mixins.

All callers should continue to use ``Memory()`` — the public API is unchanged.
Implementation is split across focused mixin modules in this package:

- ``articles.py`` — Article and summary persistence
- ``approvals.py`` — Pending approval lifecycle
- ``workflow.py`` — Workflow runs, checkpoints, revisions
- ``dashboard_queries.py`` — Dashboard read queries
- ``taxonomy.py`` — Categories and tags
- ``oauth.py`` — OAuth token encryption/storage
- ``backup.py`` — Database backup and log retention
- ``drift.py`` — Drift detection alerts
"""

import yaml

from memory.approvals import ApprovalsMixin
from memory.articles import ArticlesMixin
from memory.backup import BackupMixin
from memory.dashboard_queries import DashboardMixin
from memory.database import init_db
from memory.drift import DriftMixin
from memory.oauth import OAuthMixin
from memory.taxonomy import TaxonomyMixin
from memory.workflow import WorkflowMixin
from utils.logger.logger import setup_logger

logger = setup_logger(__name__)

DATABASE_CONFIG_PATH = 'config/database.yaml'


class Memory(
    ArticlesMixin,
    ApprovalsMixin,
    WorkflowMixin,
    DashboardMixin,
    TaxonomyMixin,
    OAuthMixin,
    BackupMixin,
    DriftMixin,
):
    """Unified interface for all persistent memory operations.

    Composes domain-specific mixins so callers can use a single ``Memory()``
    instance for every database operation.  Each mixin expects ``self.engine``
    and the relevant config attributes to be set by ``__init__``.
    """

    def __init__(self) -> None:
        """Load database config and initialize the SQLAlchemy engine."""
        with open(DATABASE_CONFIG_PATH, 'r') as f:
            config = yaml.safe_load(f)
        db_path: str = config['database']['path']
        self.db_path = db_path
        self.retention_days: int = config['database'].get('retention_days', 30)
        self.log_retention_days: int = config.get('logging', {}).get(
            'retention_days', 14
        )
        self.backup_path: str = config.get('backup', {}).get('path', 'data/backups')
        self.backup_retention_days: int = config.get('backup', {}).get(
            'retention_days', 30
        )
        self.engine = init_db(db_path)
