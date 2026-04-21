"""Shared test fixtures for the entire test suite."""

import json
import os
import sys

import pytest

# Ensure project root is on path (needed for mutmut which runs from mutants/ dir)
_this_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_this_dir)
# If running inside mutants/, go up one more level to the real project root
if os.path.basename(_project_root) == 'mutants':
    _project_root = os.path.dirname(_project_root)
sys.path.insert(0, _project_root)

from memory.database import init_db
from memory.memory import Memory

# --- Realistic mock data ---


@pytest.fixture
def mock_scores():
    """Two completed games and one scheduled game."""
    return [
        {
            'team': 'Chicago Cubs',
            'game_id': '401654321',
            'date': '2026-04-13T23:10Z',
            'season_type': 'regular-season',
            'status': 'Final',
            'status_detail': 'Final',
            'completed': True,
            'home_team': 'Chicago Cubs',
            'away_team': 'Milwaukee Brewers',
            'home_score': '5',
            'away_score': '3',
            'home_record': '8-4',
            'away_record': '6-6',
            'home_hits': 9,
            'away_hits': 7,
            'home_errors': 0,
            'away_errors': 1,
            'venue': 'Wrigley Field',
            'neutral_site': False,
            'headline': 'Cubs rally in the 7th to take series',
            'short_link_text': 'Recap',
            'game_url': 'https://www.espn.com/mlb/game/_/gameId/401654321',
        },
        {
            'team': 'Chicago White Sox',
            'game_id': '401654322',
            'date': '2026-04-13T22:10Z',
            'season_type': 'regular-season',
            'status': 'Final',
            'status_detail': 'Final',
            'completed': True,
            'home_team': 'Minnesota Twins',
            'away_team': 'Chicago White Sox',
            'home_score': '7',
            'away_score': '2',
            'home_record': '7-5',
            'away_record': '3-9',
            'home_hits': 11,
            'away_hits': 5,
            'home_errors': 0,
            'away_errors': 2,
            'venue': 'Target Field',
            'neutral_site': False,
            'headline': 'Twins cruise past White Sox',
            'short_link_text': 'Recap',
            'game_url': 'https://www.espn.com/mlb/game/_/gameId/401654322',
        },
        {
            'team': 'Chicago Bulls',
            'game_id': '401654323',
            'date': '2026-04-14T19:00Z',
            'season_type': 'regular-season',
            'status': 'Scheduled',
            'status_detail': '7:00 PM CT',
            'completed': False,
            'home_team': 'Chicago Bulls',
            'away_team': 'Cleveland Cavaliers',
            'home_score': '0',
            'away_score': '0',
            'home_record': '25-50',
            'away_record': '55-20',
            'venue': 'United Center',
            'neutral_site': False,
            'headline': 'Bulls look to end losing streak',
            'short_link_text': 'Preview',
            'game_url': 'https://www.espn.com/nba/game/_/gameId/401654323',
        },
    ]


@pytest.fixture
def mock_articles():
    """Six articles across three teams with relevance scores."""
    return [
        {
            'title': 'Cubs rally in 7th inning to beat Brewers 5-3',
            'url': 'https://example.com/cubs-rally',
            'publishedAt': '2026-04-13T23:45:00Z',
            'source': 'ESPN',
            'team': 'Chicago Cubs',
            'relevance_score': 85.5,
        },
        {
            'title': 'Suzuki homers twice in Cubs victory',
            'url': 'https://example.com/suzuki-homers',
            'publishedAt': '2026-04-14T00:15:00Z',
            'source': 'Chicago Tribune',
            'team': 'Chicago Cubs',
            'relevance_score': 78.2,
        },
        {
            'title': 'White Sox fall to Twins in series opener',
            'url': 'https://example.com/sox-fall',
            'publishedAt': '2026-04-13T23:30:00Z',
            'source': 'ESPN',
            'team': 'Chicago White Sox',
            'relevance_score': 72.0,
        },
        {
            'title': 'White Sox considering trade deadline moves',
            'url': 'https://example.com/sox-trade',
            'publishedAt': '2026-04-14T01:00:00Z',
            'source': 'The Athletic',
            'team': 'Chicago White Sox',
            'relevance_score': 65.3,
        },
        {
            'title': 'Bulls prepare for play-in tournament push',
            'url': 'https://example.com/bulls-playin',
            'publishedAt': '2026-04-14T02:00:00Z',
            'source': 'NBC Sports Chicago',
            'team': 'Chicago Bulls',
            'relevance_score': 70.1,
        },
        {
            'title': 'LaVine questionable for tonight vs Cavaliers',
            'url': 'https://example.com/lavine-injury',
            'publishedAt': '2026-04-14T10:00:00Z',
            'source': 'Chicago Sun-Times',
            'team': 'Chicago Bulls',
            'relevance_score': 68.0,
        },
    ]


@pytest.fixture
def mock_summaries():
    """Summarized versions of mock articles."""
    return [
        {
            'url': 'https://example.com/cubs-rally',
            'team': 'Chicago Cubs',
            'summary': 'The Cubs rallied in the 7th inning with a three-run homer by Seiya Suzuki to beat the Brewers 5-3 at Wrigley Field.',
            'event_type': 'game_recap',
            'players_mentioned': ['Seiya Suzuki', 'Marcus Stroman'],
            'is_relevant': True,
        },
        {
            'url': 'https://example.com/suzuki-homers',
            'team': 'Chicago Cubs',
            'summary': 'Suzuki went 3-for-4 with two home runs and four RBIs in the Cubs win over Milwaukee.',
            'event_type': 'game_recap',
            'players_mentioned': ['Seiya Suzuki'],
            'is_relevant': True,
        },
        {
            'url': 'https://example.com/sox-fall',
            'team': 'Chicago White Sox',
            'summary': 'The White Sox managed just 5 hits in a 7-2 loss to the Twins at Target Field.',
            'event_type': 'game_recap',
            'players_mentioned': ['Garrett Crochet'],
            'is_relevant': True,
        },
        {
            'url': 'https://example.com/sox-trade',
            'team': 'Chicago White Sox',
            'summary': 'Sources indicate the White Sox are exploring trade options for Garrett Crochet ahead of the deadline.',
            'event_type': 'trade',
            'players_mentioned': ['Garrett Crochet'],
            'is_relevant': True,
        },
        {
            'url': 'https://example.com/bulls-playin',
            'team': 'Chicago Bulls',
            'summary': 'The Bulls need to win two of their final three games to secure a play-in spot.',
            'event_type': 'preview',
            'players_mentioned': ['Zach LaVine', 'Coby White'],
            'is_relevant': True,
        },
        {
            'url': 'https://example.com/lavine-injury',
            'team': 'Chicago Bulls',
            'summary': 'Zach LaVine is listed as questionable for tonight with a knee contusion.',
            'event_type': 'injury',
            'players_mentioned': ['Zach LaVine'],
            'is_relevant': True,
        },
    ]


@pytest.fixture
def mock_draft():
    """A realistic blog draft output."""
    return {
        'title': 'Chicago Sports Recap — April 14, 2026',
        'content': '<h1>Chicago Sports Recap — April 14, 2026</h1><p>Big day in Chicago sports.</p>',
        'excerpt': 'Cubs rally past Brewers, White Sox fall to Twins, and Bulls prep for play-in push.',
        'teams_covered': ['Chicago Cubs', 'Chicago White Sox', 'Chicago Bulls'],
        'article_count': 6,
    }


@pytest.fixture
def mock_evaluation():
    """A realistic evaluation output."""
    return {
        'evaluation_id': '2026-04-14T06:00:00+00:00',
        'overall_score': 8.25,
        'criteria_scores': {
            'accuracy': 9.0,
            'completeness': 8.0,
            'readability': 8.5,
            'seo': 7.5,
        },
        'criteria_reasoning': {
            'accuracy': 'All scores verified correctly.',
            'completeness': 'All teams with activity covered.',
            'readability': 'Good conversational tone.',
            'seo': 'Title slightly long at 62 characters.',
        },
        'improvement_suggestions': {
            'accuracy': [],
            'completeness': [],
            'readability': [],
            'seo': ['Shorten title to 50-60 characters.'],
        },
    }


@pytest.fixture
def mock_claude_json_response(mock_draft):
    """Factory for creating mock ClaudeClient.send_message return values."""

    def _factory(data=None):
        return json.dumps(data or mock_draft)

    return _factory


# --- Database fixtures ---


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary SQLite database file, cleaned up after test."""
    db_path = str(tmp_path / 'test.db')
    init_db(db_path)
    return db_path


@pytest.fixture
def memory(tmp_db, monkeypatch):
    """Memory instance pointed at the temp database."""
    monkeypatch.setattr('memory.memory.DATABASE_CONFIG_PATH', '__nonexistent__')

    class _TestMemory(Memory):
        def __init__(self, db_path):
            self.db_path = db_path
            self.retention_days = 30
            self.log_retention_days = 30
            self.backup_path = 'data/backups'
            self.backup_retention_days = 30
            self.engine = init_db(db_path)

    return _TestMemory(tmp_db)
