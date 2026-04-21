"""Tests for tools/fetch_articles_tool.py."""

from unittest.mock import MagicMock, patch

from models.inputs.fetch_articles_input import FetchArticlesInput
from tools.fetch_articles_tool import FetchArticlesTool


class TestFetchArticlesTool:
    """Tests for FetchArticlesTool.execute."""

    @patch('tools.fetch_articles_tool.Memory')
    @patch('tools.fetch_articles_tool.yaml.safe_load')
    @patch('builtins.open')
    @patch('tools.fetch_articles_tool.SerpApiCollector')
    @patch('tools.fetch_articles_tool.NewsAPI_Collector')
    def test_deduplicates_across_sources(
        self,
        mock_news_cls,
        mock_serp_cls,
        mock_open,
        mock_yaml,
        mock_memory_cls,
        mock_articles,
    ):
        mock_yaml.return_value = {
            'collection': {'max_articles_per_source': 100},
            'relevance_scoring': {
                'weights': {
                    'recency': 0.25,
                    'source_credibility': 0.25,
                    'team_keyword_density': 0.25,
                    'content_signals': 0.25,
                },
                'credible_sources': ['ESPN'],
                'content_signal_keywords': ['trade'],
            },
        }
        # Both sources return the same article
        shared_article = mock_articles[0].copy()
        mock_news_cls.return_value.collect_articles.return_value = [shared_article]
        mock_serp_cls.return_value.collect_articles.return_value = [
            shared_article.copy()
        ]
        mock_memory = MagicMock()
        mock_memory.get_seen_urls.return_value = set()
        mock_memory_cls.return_value = mock_memory

        tool = FetchArticlesTool()
        result = tool.execute(FetchArticlesInput())

        assert result.article_count == 1  # deduplicated

    @patch('tools.fetch_articles_tool.Memory')
    @patch('tools.fetch_articles_tool.yaml.safe_load')
    @patch('builtins.open')
    @patch('tools.fetch_articles_tool.SerpApiCollector')
    @patch('tools.fetch_articles_tool.NewsAPI_Collector')
    def test_memory_filter_excludes_seen_urls(
        self,
        mock_news_cls,
        mock_serp_cls,
        mock_open,
        mock_yaml,
        mock_memory_cls,
        mock_articles,
    ):
        mock_yaml.return_value = {
            'collection': {'max_articles_per_source': 100},
            'relevance_scoring': {
                'weights': {
                    'recency': 0.25,
                    'source_credibility': 0.25,
                    'team_keyword_density': 0.25,
                    'content_signals': 0.25,
                },
                'credible_sources': [],
                'content_signal_keywords': [],
            },
        }
        mock_news_cls.return_value.collect_articles.return_value = mock_articles[:2]
        mock_serp_cls.return_value.collect_articles.return_value = []
        mock_memory = MagicMock()
        mock_memory.get_seen_urls.return_value = {mock_articles[0]['url']}
        mock_memory_cls.return_value = mock_memory

        tool = FetchArticlesTool()
        result = tool.execute(FetchArticlesInput())

        assert result.new_article_count == 1
        assert result.filtered_article_count == 1

    @patch('tools.fetch_articles_tool.Memory')
    @patch('tools.fetch_articles_tool.yaml.safe_load')
    @patch('builtins.open')
    @patch('tools.fetch_articles_tool.SerpApiCollector')
    @patch('tools.fetch_articles_tool.NewsAPI_Collector')
    def test_force_refresh_skips_memory_filter(
        self,
        mock_news_cls,
        mock_serp_cls,
        mock_open,
        mock_yaml,
        mock_memory_cls,
        mock_articles,
    ):
        mock_yaml.return_value = {
            'collection': {'max_articles_per_source': 100},
            'relevance_scoring': {
                'weights': {
                    'recency': 0.25,
                    'source_credibility': 0.25,
                    'team_keyword_density': 0.25,
                    'content_signals': 0.25,
                },
                'credible_sources': [],
                'content_signal_keywords': [],
            },
        }
        mock_news_cls.return_value.collect_articles.return_value = mock_articles[:2]
        mock_serp_cls.return_value.collect_articles.return_value = []
        mock_memory = MagicMock()
        mock_memory_cls.return_value = mock_memory

        tool = FetchArticlesTool()
        result = tool.execute(FetchArticlesInput(force_refresh=True))

        assert result.new_article_count == 2
        assert result.filtered_article_count == 0
        mock_memory.get_seen_urls.assert_not_called()


class TestFetchArticlesToolErrorPaths:
    """Tests for error handling and edge cases in FetchArticlesTool."""

    @patch('tools.fetch_articles_tool.Memory')
    @patch('tools.fetch_articles_tool.yaml.safe_load')
    @patch('builtins.open')
    @patch('tools.fetch_articles_tool.SerpApiCollector')
    @patch('tools.fetch_articles_tool.NewsAPI_Collector')
    def test_captures_collector_errors(
        self, mock_news_cls, mock_serp_cls, mock_open, mock_yaml, mock_memory_cls
    ):
        mock_yaml.return_value = {
            'collection': {'max_articles_per_source': 100},
            'relevance_scoring': {
                'weights': {
                    'recency': 0.25,
                    'source_credibility': 0.25,
                    'team_keyword_density': 0.25,
                    'content_signals': 0.25,
                },
                'credible_sources': [],
                'content_signal_keywords': [],
            },
        }
        mock_news_cls.return_value.collect_articles.side_effect = Exception(
            'NewsAPI down'
        )
        mock_serp_cls.return_value.collect_articles.return_value = []
        mock_memory = MagicMock()
        mock_memory.get_seen_urls.return_value = set()
        mock_memory_cls.return_value = mock_memory

        tool = FetchArticlesTool()
        result = tool.execute(FetchArticlesInput())

        assert len(result.errors) == 1
        assert 'NewsAPI down' in result.errors[0]

    @patch('tools.fetch_articles_tool.Memory')
    @patch('tools.fetch_articles_tool.yaml.safe_load')
    @patch('builtins.open')
    @patch('tools.fetch_articles_tool.SerpApiCollector')
    @patch('tools.fetch_articles_tool.NewsAPI_Collector')
    def test_persists_error_api_call_result(
        self, mock_news_cls, mock_serp_cls, mock_open, mock_yaml, mock_memory_cls
    ):
        mock_yaml.return_value = {
            'collection': {'max_articles_per_source': 100},
            'relevance_scoring': {
                'weights': {
                    'recency': 0.25,
                    'source_credibility': 0.25,
                    'team_keyword_density': 0.25,
                    'content_signals': 0.25,
                },
                'credible_sources': [],
                'content_signal_keywords': [],
            },
        }
        mock_news_cls.return_value.collect_articles.side_effect = Exception('fail')
        mock_serp_cls.return_value.collect_articles.return_value = []
        mock_memory = MagicMock()
        mock_memory.get_seen_urls.return_value = set()
        mock_memory.get_workflow_run_db_id.return_value = 7
        mock_memory_cls.return_value = mock_memory

        tool = FetchArticlesTool()
        tool.execute(FetchArticlesInput(run_id='test-run'))

        mock_memory.save_api_call_result.assert_any_call(
            7, 'newsapi', 'error', error='fail'
        )

    @patch('tools.fetch_articles_tool.Memory')
    @patch('tools.fetch_articles_tool.yaml.safe_load')
    @patch('builtins.open')
    @patch('tools.fetch_articles_tool.SerpApiCollector')
    @patch('tools.fetch_articles_tool.NewsAPI_Collector')
    def test_recency_score_handles_bad_date(
        self, mock_news_cls, mock_serp_cls, mock_open, mock_yaml, mock_memory_cls
    ):
        mock_yaml.return_value = {
            'collection': {'max_articles_per_source': 100},
            'relevance_scoring': {
                'weights': {
                    'recency': 1.0,
                    'source_credibility': 0,
                    'team_keyword_density': 0,
                    'content_signals': 0,
                },
                'credible_sources': [],
                'content_signal_keywords': [],
            },
        }
        mock_memory_cls.return_value = MagicMock()

        tool = FetchArticlesTool()
        # Bad date format
        assert tool._score_recency('not-a-date') == 0.0
        # None
        assert tool._score_recency(None) == 0.0

    @patch('tools.fetch_articles_tool.Memory')
    @patch('tools.fetch_articles_tool.yaml.safe_load')
    @patch('builtins.open')
    @patch('tools.fetch_articles_tool.SerpApiCollector')
    @patch('tools.fetch_articles_tool.NewsAPI_Collector')
    def test_keyword_density_empty_inputs(
        self, mock_news_cls, mock_serp_cls, mock_open, mock_yaml, mock_memory_cls
    ):
        mock_yaml.return_value = {
            'collection': {'max_articles_per_source': 100},
            'relevance_scoring': {
                'weights': {
                    'recency': 0.25,
                    'source_credibility': 0.25,
                    'team_keyword_density': 0.25,
                    'content_signals': 0.25,
                },
                'credible_sources': [],
                'content_signal_keywords': [],
            },
        }
        mock_memory_cls.return_value = MagicMock()

        tool = FetchArticlesTool()
        assert tool._score_keyword_density('', ['cubs']) == 0.0
        assert tool._score_keyword_density('Cubs win', []) == 0.0
        assert tool._score_content_signals('', ['trade']) == 0.0
