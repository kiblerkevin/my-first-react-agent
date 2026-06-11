"""Lambda configuration from environment variables.

All config that was previously in YAML files is now read from env vars.
Static config (team lists, scoring weights) is defined as constants here.
"""

import json
import os


def env(key: str, default: str = '') -> str:
    """Read a string environment variable."""
    return os.environ.get(key, default)


def env_int(key: str, default: int = 0) -> int:
    """Read an integer environment variable."""
    return int(os.environ.get(key, str(default)))


def env_float(key: str, default: float = 0.0) -> float:
    """Read a float environment variable."""
    return float(os.environ.get(key, str(default)))


# --- Table prefix ---
TABLE_PREFIX = env('TABLE_PREFIX', 'chicago-sports-recap-dev')
ENVIRONMENT = env('ENVIRONMENT', 'dev')

# --- Collection config (from sources.yaml) ---
MAX_ARTICLES_PER_SOURCE = env_int('MAX_ARTICLES_PER_SOURCE', 100)
LOOKBACK_HOURS = env_int('LOOKBACK_HOURS', 24)

# --- LLM models (from llms.yaml) ---
LLM_SUMMARIZER_MODEL = env('LLM_SUMMARIZER_MODEL', 'claude-haiku-4-5')
LLM_SUMMARIZER_TEMPERATURE = env_float('LLM_SUMMARIZER_TEMPERATURE', 0.1)
LLM_SUMMARIZER_MAX_TOKENS = env_int('LLM_SUMMARIZER_MAX_TOKENS', 512)

LLM_DRAFTER_MODEL = env('LLM_DRAFTER_MODEL', 'claude-sonnet-4-5')
LLM_DRAFTER_TEMPERATURE = env_float('LLM_DRAFTER_TEMPERATURE', 0.5)
LLM_DRAFTER_MAX_TOKENS = env_int('LLM_DRAFTER_MAX_TOKENS', 4096)

LLM_EVALUATOR_MODEL = env('LLM_EVALUATOR_MODEL', 'claude-sonnet-4-5')
LLM_EVALUATOR_TEMPERATURE = env_float('LLM_EVALUATOR_TEMPERATURE', 0.1)
LLM_EVALUATOR_MAX_TOKENS = env_int('LLM_EVALUATOR_MAX_TOKENS', 2048)

LLM_ORCHESTRATOR_MODEL = env('LLM_ORCHESTRATOR_MODEL', 'claude-sonnet-4-5')
LLM_ORCHESTRATOR_TEMPERATURE = env_float('LLM_ORCHESTRATOR_TEMPERATURE', 0.2)
LLM_ORCHESTRATOR_MAX_TOKENS = env_int('LLM_ORCHESTRATOR_MAX_TOKENS', 4096)

LLM_FALLBACK_MODEL = env('LLM_FALLBACK_MODEL', 'gemini-2.5-flash')
LLM_FALLBACK_PRO_MODEL = env('LLM_FALLBACK_PRO_MODEL', 'gemini-2.5-pro')

# --- Revision loop (from orchestration.yaml) ---
REVISION_MAX_TOOL_CALLS = env_int('REVISION_MAX_TOOL_CALLS', 6)
REVISION_CRITERION_FLOORS: dict[str, float] = json.loads(
    env(
        'REVISION_CRITERION_FLOORS',
        '{"accuracy": 8.0, "completeness": 7.0, "readability": 7.0, "seo": 6.0}',
    )
)

# --- Approval ---
APPROVAL_EXPIRY_HOURS = env_int('APPROVAL_EXPIRY_HOURS', 24)

# --- Rate limiting ---
RATE_LIMIT_MAX_RETRIES = env_int('RATE_LIMIT_MAX_RETRIES', 3)
RATE_LIMIT_BASE_DELAY = env_float('RATE_LIMIT_BASE_DELAY', 1.0)

# --- Langfuse ---
LANGFUSE_HOST = env('LANGFUSE_HOST', 'https://cloud.langfuse.com')

# --- Static config: ESPN teams (from sources.yaml) ---
ESPN_TEAMS = [
    {'name': 'Chicago Bears', 'sport': 'football', 'league': 'nfl', 'team_id': 3},
    {'name': 'Chicago Bulls', 'sport': 'basketball', 'league': 'nba', 'team_id': 4},
    {'name': 'Chicago Cubs', 'sport': 'baseball', 'league': 'mlb', 'team_id': 16},
    {'name': 'Chicago White Sox', 'sport': 'baseball', 'league': 'mlb', 'team_id': 4},
    {'name': 'Chicago Blackhawks', 'sport': 'hockey', 'league': 'nhl', 'team_id': 4},
    {'name': 'Chicago Fire FC', 'sport': 'soccer', 'league': 'usa.1', 'team_id': 182},
    {'name': 'Chicago Sky', 'sport': 'basketball', 'league': 'wnba', 'team_id': 19},
    {
        'name': 'Chicago Stars FC',
        'sport': 'soccer',
        'league': 'usa.nwsl',
        'team_id': 15360,
    },
]

# --- Static config: Relevance scoring (from sources.yaml) ---
SCORING_WEIGHTS = {
    'recency': 0.35,
    'source_credibility': 0.25,
    'team_keyword_density': 0.25,
    'content_signals': 0.15,
}

CREDIBLE_SOURCES = [
    'ESPN',
    'MLB.com',
    'NBA.com',
    'NHL.com',
    'Chicago Tribune',
    'Chicago Sun-Times',
    'Bleacher Report',
    'The Athletic',
    'CBS Sports',
    'NBC Sports',
    'Sports Illustrated',
    'Yahoo Sports',
    'Associated Press',
]

CONTENT_SIGNAL_KEYWORDS = [
    'recap',
    'score',
    'highlights',
    'final',
    'win',
    'loss',
    'game',
    'match',
    'result',
    'victory',
    'defeat',
]

# --- Static config: Teams (from sources.yaml) ---
TEAMS = [
    {
        'name': 'Chicago Bulls',
        'sport': 'basketball',
        'league': 'NBA',
        'keywords': ['bulls', 'chicago bulls', 'nba chicago'],
    },
    {
        'name': 'Chicago Bears',
        'sport': 'football',
        'league': 'NFL',
        'keywords': ['bears', 'chicago bears', 'nfl chicago'],
    },
    {
        'name': 'Chicago Cubs',
        'sport': 'baseball',
        'league': 'MLB',
        'keywords': ['cubs', 'chicago cubs', 'mlb chicago', 'wrigley'],
    },
    {
        'name': 'Chicago White Sox',
        'sport': 'baseball',
        'league': 'MLB',
        'keywords': ['white sox', 'chicago white sox', 'sox', 'guaranteed rate'],
    },
    {
        'name': 'Chicago Blackhawks',
        'sport': 'hockey',
        'league': 'NHL',
        'keywords': ['blackhawks', 'chicago blackhawks', 'hawks', 'nhl chicago'],
    },
    {
        'name': 'Chicago Fire',
        'sport': 'soccer',
        'league': 'MLS',
        'keywords': ['fire', 'chicago fire', 'mls chicago'],
    },
    {
        'name': 'Chicago Sky',
        'sport': 'basketball',
        'league': 'WNBA',
        'keywords': ['sky', 'chicago sky', 'wnba chicago'],
    },
    {
        'name': 'Chicago Stars',
        'sport': 'soccer',
        'league': 'NWSL',
        'keywords': ['stars', 'chicago stars', 'nwsl chicago'],
    },
    {
        'name': 'Chicago Hounds',
        'sport': 'rugby',
        'league': 'MLR',
        'keywords': ['hounds', 'chicago hounds', 'mlr chicago'],
    },
]

# --- DynamoDB table names (derived from prefix) ---
TABLE_ARTICLES = f'{TABLE_PREFIX}-articles'
TABLE_ARTICLE_SUMMARIES = f'{TABLE_PREFIX}-article-summaries'
TABLE_SUMMARIES = f'{TABLE_PREFIX}-summaries'
TABLE_PENDING_APPROVALS = f'{TABLE_PREFIX}-pending-approvals'
TABLE_WORKFLOW_RUNS = f'{TABLE_PREFIX}-workflow-runs'
TABLE_DRIFT_ALERTS = f'{TABLE_PREFIX}-drift-alerts'
TABLE_OAUTH_TOKENS = f'{TABLE_PREFIX}-oauth-tokens'
TABLE_EVALUATIONS = f'{TABLE_PREFIX}-evaluations'
TABLE_SUMMARY_STATS = f'{TABLE_PREFIX}-summary-stats'
TABLE_API_CALL_RESULTS = f'{TABLE_PREFIX}-api-call-results'
TABLE_CATEGORIES = f'{TABLE_PREFIX}-categories'
TABLE_TAGS = f'{TABLE_PREFIX}-tags'
TABLE_SUMMARY_TAGS = f'{TABLE_PREFIX}-summary-tags'
TABLE_IMPROVEMENT_SUGGESTIONS = f'{TABLE_PREFIX}-improvement-suggestions'
