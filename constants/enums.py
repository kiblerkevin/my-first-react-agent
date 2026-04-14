from enum import Enum

class ApiSource(Enum):
    NEWSAPI = 'newsapi'
    SERPAPI ='serpapi'
    
class RssSource(Enum):
    ESPN = 'espn'
    CHICAGO_TRIBUNE = 'chicago_tribune'
    CHICAGO_SUN_TIMES = 'chicago_sun_times'
    BLEACHER_REPORT = 'bleacher_report'