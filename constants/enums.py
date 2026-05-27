"""Enum definitions for API sources, RSS sources, and event types."""

from enum import Enum


class ApiSource(Enum):
    """External API data sources."""

    NEWSAPI = 'newsapi'
    SERPAPI = 'serpapi'
    ESPNAPI = 'espnapi'


class RssSource(Enum):
    """RSS feed data sources."""

    ESPN = 'espn'
    CHICAGO_TRIBUNE = 'chicago_tribune'
    CHICAGO_SUN_TIMES = 'chicago_sun_times'
    BLEACHER_REPORT = 'bleacher_report'


class EventType(Enum):
    """Article event type classifications."""

    GAME_RECAP = 'game_recap'
    TRADE = 'trade'
    INJURY = 'injury'
    DRAFT = 'draft'
    ROSTER = 'roster'
    OPINION = 'opinion'
    PREVIEW = 'preview'
    OTHER = 'other'


class WorkflowStatus(Enum):
    """Workflow run status values."""

    RUNNING = 'running'
    SUCCESS = 'success'
    FAILED = 'failed'
    SKIPPED = 'skipped'


class ApprovalStatus(Enum):
    """Pending approval status values."""

    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    EXPIRED = 'expired'


class ApiCallStatus(Enum):
    """API call result status values."""

    SUCCESS = 'success'
    ERROR = 'error'


class DriftAlertStatus(Enum):
    """Drift alert status values."""

    ACTIVE = 'active'
    RESOLVED = 'resolved'
