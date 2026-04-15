from enum import Enum

class ApiSource(Enum):
    NEWSAPI = 'newsapi'
    SERPAPI = 'serpapi'
    ESPNAPI = 'espnapi'

class RssSource(Enum):
    ESPN = 'espn'
    CHICAGO_TRIBUNE = 'chicago_tribune'
    CHICAGO_SUN_TIMES = 'chicago_sun_times'
    BLEACHER_REPORT = 'bleacher_report'

class EventType(Enum):
    GAME_RECAP = 'game_recap'
    TRADE = 'trade'
    INJURY = 'injury'
    DRAFT = 'draft'
    ROSTER = 'roster'
    OPINION = 'opinion'
    PREVIEW = 'preview'
    OTHER = 'other'