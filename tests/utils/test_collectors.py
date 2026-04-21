"""Tests for article collectors."""

from unittest.mock import MagicMock, patch

from utils.article_collectors.api_collectors.espn_collector import ESPNCollector
from utils.article_collectors.api_collectors.newsapi_collector import NewsAPI_Collector
from utils.article_collectors.api_collectors.serpapi_collector import SerpApiCollector


class TestESPNCollector:
    """Tests for ESPNCollector.collect_articles."""

    @patch('utils.article_collectors.api_collectors.api_collector.yaml.safe_load')
    @patch('builtins.open')
    @patch(
        'utils.article_collectors.api_collectors.espn_collector.rate_limited_request'
    )
    def test_parses_scores_from_espn_response(self, mock_request, mock_open, mock_yaml):
        mock_yaml.return_value = {
            'apis': {
                'espnapi': {
                    'url': 'http://espn.test',
                    'chicago_teams': [
                        {
                            'name': 'Chicago Cubs',
                            'sport': 'baseball',
                            'league': 'mlb',
                            'team_id': 16,
                        }
                    ],
                }
            },
            'collection': {'lookback_hours': 24, 'timeout_seconds': 10},
        }
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = {
            'events': [
                {
                    'id': '123',
                    'date': '2026-04-13T23:00Z',
                    'season': {'slug': 'regular-season'},
                    'links': [{'rel': ['summary'], 'href': 'http://espn.com/game/123'}],
                    'competitions': [
                        {
                            'status': {
                                'type': {
                                    'description': 'Final',
                                    'shortDetail': 'Final',
                                    'completed': True,
                                }
                            },
                            'competitors': [
                                {
                                    'homeAway': 'home',
                                    'team': {'id': '16', 'displayName': 'Chicago Cubs'},
                                    'score': '5',
                                    'records': [{'type': 'total', 'summary': '8-4'}],
                                },
                                {
                                    'homeAway': 'away',
                                    'team': {
                                        'id': '8',
                                        'displayName': 'Milwaukee Brewers',
                                    },
                                    'score': '3',
                                    'records': [{'type': 'total', 'summary': '6-6'}],
                                },
                            ],
                            'venue': {'fullName': 'Wrigley Field'},
                            'neutralSite': False,
                            'headlines': [
                                {'description': 'Cubs win', 'shortLinkText': 'Recap'}
                            ],
                        }
                    ],
                }
            ],
        }
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        collector = ESPNCollector()
        scores = collector.collect_articles()

        assert len(scores) == 1
        assert scores[0]['team'] == 'Chicago Cubs'
        assert scores[0]['home_score'] == '5'
        assert scores[0]['completed'] is True

    @patch('utils.article_collectors.api_collectors.api_collector.yaml.safe_load')
    @patch('builtins.open')
    @patch(
        'utils.article_collectors.api_collectors.espn_collector.rate_limited_request'
    )
    def test_skips_games_without_chicago_team(self, mock_request, mock_open, mock_yaml):
        mock_yaml.return_value = {
            'apis': {
                'espnapi': {
                    'url': 'http://espn.test',
                    'chicago_teams': [
                        {
                            'name': 'Chicago Cubs',
                            'sport': 'baseball',
                            'league': 'mlb',
                            'team_id': 16,
                        }
                    ],
                }
            },
            'collection': {'lookback_hours': 24, 'timeout_seconds': 10},
        }
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = {
            'events': [
                {
                    'id': '999',
                    'date': '2026-04-13T23:00Z',
                    'season': {'slug': 'regular-season'},
                    'links': [],
                    'competitions': [
                        {
                            'status': {
                                'type': {'description': 'Final', 'completed': True}
                            },
                            'competitors': [
                                {
                                    'homeAway': 'home',
                                    'team': {'id': '1', 'displayName': 'Team A'},
                                    'score': '3',
                                },
                                {
                                    'homeAway': 'away',
                                    'team': {'id': '2', 'displayName': 'Team B'},
                                    'score': '1',
                                },
                            ],
                            'venue': {'fullName': 'Some Park'},
                            'neutralSite': False,
                            'headlines': [],
                        }
                    ],
                }
            ],
        }
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        collector = ESPNCollector()
        scores = collector.collect_articles()

        assert len(scores) == 0


class TestNewsAPICollector:
    """Tests for NewsAPI_Collector.collect_articles."""

    @patch('utils.article_collectors.api_collectors.api_collector.yaml.safe_load')
    @patch('builtins.open')
    @patch(
        'utils.article_collectors.api_collectors.newsapi_collector.rate_limited_request'
    )
    def test_collects_and_deduplicates(self, mock_request, mock_open, mock_yaml):
        mock_yaml.return_value = {
            'apis': {
                'newsapi': {
                    'url': 'http://newsapi.test',
                    'env_key_name': 'NEWSAPI_KEY',
                    'language': 'en',
                    'page_size': 10,
                    'sort_by': 'publishedAt',
                }
            },
            'teams': [{'name': 'Chicago Cubs'}],
            'collection': {'lookback_hours': 24, 'timeout_seconds': 10},
        }
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = {
            'articles': [
                {
                    'title': 'Cubs win',
                    'url': 'http://a.com',
                    'publishedAt': '2026-04-14T00:00:00Z',
                    'source': {'name': 'ESPN'},
                    'content': 'Article text',
                },
                {
                    'title': 'Cubs win again',
                    'url': 'http://b.com',
                    'publishedAt': '2026-04-14T01:00:00Z',
                    'source': {'name': 'ESPN'},
                    'content': 'More text',
                },
            ],
        }
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        with patch.dict('os.environ', {'NEWSAPI_KEY': 'fake-key'}):
            collector = NewsAPI_Collector()
        articles = collector.collect_articles()

        assert len(articles) == 2
        assert articles[0]['team'] == 'Chicago Cubs'

    @patch('utils.article_collectors.api_collectors.api_collector.yaml.safe_load')
    @patch('builtins.open')
    @patch(
        'utils.article_collectors.api_collectors.newsapi_collector.rate_limited_request'
    )
    def test_skips_removed_content(self, mock_request, mock_open, mock_yaml):
        mock_yaml.return_value = {
            'apis': {
                'newsapi': {
                    'url': 'http://newsapi.test',
                    'env_key_name': 'NEWSAPI_KEY',
                    'language': 'en',
                    'page_size': 10,
                    'sort_by': 'publishedAt',
                }
            },
            'teams': [{'name': 'Cubs'}],
            'collection': {'lookback_hours': 24, 'timeout_seconds': 10},
        }
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = {
            'articles': [
                {
                    'title': 'Removed article',
                    'url': 'http://x.com',
                    'publishedAt': '2026-04-14T00:00:00Z',
                    'source': {'name': 'X'},
                    'content': 'Removed',
                    'description': '',
                },
            ],
        }
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        with patch.dict('os.environ', {'NEWSAPI_KEY': 'fake-key'}):
            collector = NewsAPI_Collector()
        articles = collector.collect_articles()

        assert len(articles) == 0


class TestSerpApiCollector:
    """Tests for SerpApiCollector.collect_articles."""

    @patch('builtins.open')
    @patch('utils.article_collectors.api_collectors.serpapi_collector.serpapi.Client')
    def test_collects_news_results(self, mock_client_cls, mock_open):
        api_config = {
            'apis': {
                'serpapi': {'url': 'http://serp.test', 'env_key_name': 'SERPAPI_KEY'}
            },
            'teams': [{'name': 'Chicago Cubs'}],
            'collection': {'lookback_hours': 24, 'timeout_seconds': 10},
        }
        orch_config = {'rate_limiting': {'max_retries': 1, 'base_delay_seconds': 0.01}}

        mock_client = MagicMock()
        mock_client.search.return_value = {
            'news_results': [
                {
                    'title': 'Cubs trade news',
                    'link': 'http://a.com',
                    'iso_date': '2099-04-14T00:00:00Z',
                    'source': {'name': 'ESPN'},
                },
            ],
            'sports_results': [],
        }
        mock_client_cls.return_value = mock_client

        with (
            patch('yaml.safe_load', side_effect=[api_config, orch_config]),
            patch.dict('os.environ', {'SERPAPI_KEY': 'fake-key'}),
        ):
            collector = SerpApiCollector()
        articles = collector.collect_articles()

        assert len(articles) == 1
        assert articles[0]['team'] == 'Chicago Cubs'
        assert articles[0]['url'] == 'http://a.com'


class TestSerpApiCollectorRetry:
    """Tests for SerpApiCollector retry and filtering logic."""

    @patch('builtins.open')
    @patch('utils.article_collectors.api_collectors.serpapi_collector.serpapi.Client')
    @patch('utils.article_collectors.api_collectors.serpapi_collector.time.sleep')
    def test_retries_on_429(self, mock_sleep, mock_client_cls, mock_open):
        api_config = {
            'apis': {
                'serpapi': {'url': 'http://serp.test', 'env_key_name': 'SERPAPI_KEY'}
            },
            'teams': [{'name': 'Cubs'}],
            'collection': {'lookback_hours': 24, 'timeout_seconds': 10},
        }
        orch_config = {'rate_limiting': {'max_retries': 2, 'base_delay_seconds': 0.01}}

        mock_client = MagicMock()
        # First call raises 429, second succeeds
        mock_client.search.side_effect = [
            Exception('429 Too Many Requests'),
            {
                'news_results': [
                    {
                        'title': 'X',
                        'link': 'http://x.com',
                        'iso_date': '2099-01-01T00:00:00Z',
                        'source': {'name': 'Y'},
                    }
                ],
                'sports_results': [],
            },
        ]
        mock_client_cls.return_value = mock_client

        with (
            patch('yaml.safe_load', side_effect=[api_config, orch_config]),
            patch.dict('os.environ', {'SERPAPI_KEY': 'key'}),
        ):
            collector = SerpApiCollector()

        articles = collector.collect_articles()
        assert len(articles) == 1
        mock_sleep.assert_called_once()

    @patch('builtins.open')
    @patch('utils.article_collectors.api_collectors.serpapi_collector.serpapi.Client')
    def test_filters_old_articles_by_cutoff(self, mock_client_cls, mock_open):
        api_config = {
            'apis': {
                'serpapi': {'url': 'http://serp.test', 'env_key_name': 'SERPAPI_KEY'}
            },
            'teams': [{'name': 'Cubs'}],
            'collection': {'lookback_hours': 24, 'timeout_seconds': 10},
        }
        orch_config = {'rate_limiting': {'max_retries': 1, 'base_delay_seconds': 0.01}}

        mock_client = MagicMock()
        mock_client.search.return_value = {
            'news_results': [
                {
                    'title': 'Old',
                    'link': 'http://old.com',
                    'iso_date': '2020-01-01T00:00:00Z',
                    'source': {'name': 'X'},
                },
                {
                    'title': 'New',
                    'link': 'http://new.com',
                    'iso_date': '2099-01-01T00:00:00Z',
                    'source': {'name': 'X'},
                },
            ],
            'sports_results': [],
        }
        mock_client_cls.return_value = mock_client

        with (
            patch('yaml.safe_load', side_effect=[api_config, orch_config]),
            patch.dict('os.environ', {'SERPAPI_KEY': 'key'}),
        ):
            collector = SerpApiCollector()

        articles = collector.collect_articles()
        assert len(articles) == 1
        assert articles[0]['url'] == 'http://new.com'

    @patch('builtins.open')
    @patch('utils.article_collectors.api_collectors.serpapi_collector.serpapi.Client')
    def test_handles_collector_exception(self, mock_client_cls, mock_open):
        api_config = {
            'apis': {
                'serpapi': {'url': 'http://serp.test', 'env_key_name': 'SERPAPI_KEY'}
            },
            'teams': [{'name': 'Cubs'}],
            'collection': {'lookback_hours': 24, 'timeout_seconds': 10},
        }
        orch_config = {'rate_limiting': {'max_retries': 0, 'base_delay_seconds': 0.01}}

        mock_client = MagicMock()
        mock_client.search.side_effect = Exception('API error')
        mock_client_cls.return_value = mock_client

        with (
            patch('yaml.safe_load', side_effect=[api_config, orch_config]),
            patch.dict('os.environ', {'SERPAPI_KEY': 'key'}),
        ):
            collector = SerpApiCollector()

        articles = collector.collect_articles()
        assert articles == []


class TestESPNCollectorEdgeCases:
    """Tests for ESPN collector error handling."""

    @patch('utils.article_collectors.api_collectors.api_collector.yaml.safe_load')
    @patch('builtins.open')
    @patch(
        'utils.article_collectors.api_collectors.espn_collector.rate_limited_request'
    )
    def test_handles_api_error_gracefully(self, mock_request, mock_open, mock_yaml):
        mock_yaml.return_value = {
            'apis': {
                'espnapi': {
                    'url': 'http://espn.test',
                    'chicago_teams': [
                        {
                            'name': 'Cubs',
                            'sport': 'baseball',
                            'league': 'mlb',
                            'team_id': 16,
                        }
                    ],
                }
            },
            'collection': {'lookback_hours': 24, 'timeout_seconds': 10},
        }
        mock_request.side_effect = Exception('Network timeout')

        collector = ESPNCollector()
        scores = collector.collect_articles()
        assert scores == []

    @patch('utils.article_collectors.api_collectors.api_collector.yaml.safe_load')
    @patch('builtins.open')
    @patch(
        'utils.article_collectors.api_collectors.espn_collector.rate_limited_request'
    )
    def test_returns_none_when_no_home_away(self, mock_request, mock_open, mock_yaml):
        """Line 99: _parse_score returns None when home/away missing."""
        mock_yaml.return_value = {
            'apis': {
                'espnapi': {
                    'url': 'http://espn.test',
                    'chicago_teams': [
                        {
                            'name': 'Cubs',
                            'sport': 'baseball',
                            'league': 'mlb',
                            'team_id': 16,
                        }
                    ],
                }
            },
            'collection': {'lookback_hours': 24, 'timeout_seconds': 10},
        }

        collector = ESPNCollector()
        # Competitors with homeAway but neither is 'home'
        result = collector._parse_score(
            event={'id': '1', 'date': '2026-01-01', 'season': {}, 'links': []},
            competition={
                'status': {'type': {}},
                'venue': {},
                'neutralSite': False,
                'headlines': [],
            },
            competitors=[
                {
                    'homeAway': 'neutral',
                    'team': {'id': '16', 'displayName': 'Cubs'},
                    'score': '0',
                },
                {
                    'homeAway': 'neutral',
                    'team': {'id': '8', 'displayName': 'Other'},
                    'score': '0',
                },
            ],
            chicago_team_name='Cubs',
        )
        assert result is None


class TestNewsAPICollectorEdgeCases:
    """Tests for NewsAPI collector edge cases."""

    @patch('utils.article_collectors.api_collectors.api_collector.yaml.safe_load')
    @patch('builtins.open')
    @patch(
        'utils.article_collectors.api_collectors.newsapi_collector.rate_limited_request'
    )
    def test_handles_api_error(self, mock_request, mock_open, mock_yaml):
        mock_yaml.return_value = {
            'apis': {
                'newsapi': {
                    'url': 'http://newsapi.test',
                    'env_key_name': 'NEWSAPI_KEY',
                    'language': 'en',
                    'page_size': 10,
                    'sort_by': 'publishedAt',
                }
            },
            'teams': [{'name': 'Cubs'}],
            'collection': {'lookback_hours': 24, 'timeout_seconds': 10},
        }
        mock_request.side_effect = Exception('API error')

        with patch.dict('os.environ', {'NEWSAPI_KEY': 'key'}):
            collector = NewsAPI_Collector()
        articles = collector.collect_articles()
        assert articles == []

    @patch('utils.article_collectors.api_collectors.api_collector.yaml.safe_load')
    @patch('builtins.open')
    @patch(
        'utils.article_collectors.api_collectors.newsapi_collector.rate_limited_request'
    )
    def test_deduplicates_urls_across_teams(self, mock_request, mock_open, mock_yaml):
        """Line 56: skips duplicate URLs."""
        mock_yaml.return_value = {
            'apis': {
                'newsapi': {
                    'url': 'http://newsapi.test',
                    'env_key_name': 'NEWSAPI_KEY',
                    'language': 'en',
                    'page_size': 10,
                    'sort_by': 'publishedAt',
                }
            },
            'teams': [{'name': 'Cubs'}, {'name': 'Sox'}],
            'collection': {'lookback_hours': 24, 'timeout_seconds': 10},
        }
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = {
            'articles': [
                {
                    'title': 'Same article',
                    'url': 'http://same.com',
                    'publishedAt': '2026-01-01T00:00:00Z',
                    'source': {'name': 'X'},
                    'content': 'Text',
                },
            ],
        }
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        with patch.dict('os.environ', {'NEWSAPI_KEY': 'key'}):
            collector = NewsAPI_Collector()
        articles = collector.collect_articles()
        # Same URL returned for both teams, should only appear once
        assert len(articles) == 1


class TestBaseTool:
    """Test BaseTool.execute raises NotImplementedError."""

    def test_execute_raises(self):
        import pytest

        from tools.base_tool import BaseTool

        tool = BaseTool(name='x', description='x', input_schema={}, output_schema={})
        with pytest.raises(NotImplementedError):
            tool.execute(None)


class TestAPICollectorBase:
    """Test APICollector.collect_articles returns empty list."""

    @patch('utils.article_collectors.api_collectors.api_collector.yaml.safe_load')
    @patch('builtins.open')
    def test_collect_articles_returns_empty(self, mock_open, mock_yaml):
        from utils.article_collectors.api_collectors.api_collector import APICollector

        mock_yaml.return_value = {
            'apis': {'test': {'url': 'http://test.com'}},
            'collection': {'lookback_hours': 24, 'timeout_seconds': 10},
        }
        with patch.dict('os.environ', {}):
            collector = APICollector('test')
        assert collector.collect_articles() == []


class TestSerpApiCollectorDedup:
    """Test SerpAPI URL deduplication within a single team."""

    @patch('builtins.open')
    @patch('utils.article_collectors.api_collectors.serpapi_collector.serpapi.Client')
    def test_deduplicates_urls_within_results(self, mock_client_cls, mock_open):
        """Line 86: skips articles with duplicate URLs."""
        api_config = {
            'apis': {
                'serpapi': {'url': 'http://serp.test', 'env_key_name': 'SERPAPI_KEY'}
            },
            'teams': [{'name': 'Cubs'}],
            'collection': {'lookback_hours': 24, 'timeout_seconds': 10},
        }
        orch_config = {'rate_limiting': {'max_retries': 1, 'base_delay_seconds': 0.01}}

        mock_client = MagicMock()
        mock_client.search.return_value = {
            'news_results': [
                {
                    'title': 'A',
                    'link': 'http://same.com',
                    'iso_date': '2099-01-01T00:00:00Z',
                    'source': {'name': 'X'},
                },
                {
                    'title': 'B',
                    'link': 'http://same.com',
                    'iso_date': '2099-01-01T00:00:00Z',
                    'source': {'name': 'Y'},
                },
            ],
            'sports_results': [],
        }
        mock_client_cls.return_value = mock_client

        with (
            patch('yaml.safe_load', side_effect=[api_config, orch_config]),
            patch.dict('os.environ', {'SERPAPI_KEY': 'key'}),
        ):
            collector = SerpApiCollector()

        articles = collector.collect_articles()
        assert len(articles) == 1  # second URL skipped
