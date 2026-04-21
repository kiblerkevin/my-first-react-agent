"""Tests for relevance scoring logic in FetchArticlesTool."""

from unittest.mock import patch

from tools.fetch_articles_tool import FetchArticlesTool


def _make_tool(scoring_config=None):
    """Create a FetchArticlesTool with mocked dependencies."""
    default_scoring = {
        'weights': {
            'recency': 0.3,
            'source_credibility': 0.25,
            'team_keyword_density': 0.25,
            'content_signals': 0.2,
        },
        'credible_sources': ['ESPN', 'The Athletic'],
        'content_signal_keywords': ['trade', 'injury', 'homer'],
    }
    config = {
        'collection': {'max_articles_per_source': 100},
        'relevance_scoring': scoring_config or default_scoring,
    }
    with (
        patch('tools.fetch_articles_tool.yaml.safe_load', return_value=config),
        patch('builtins.open'),
        patch('tools.fetch_articles_tool.NewsAPI_Collector'),
        patch('tools.fetch_articles_tool.SerpApiCollector'),
        patch('tools.fetch_articles_tool.Memory'),
    ):
        return FetchArticlesTool()


class TestRelevanceScoring:
    """Tests for the scoring methods on FetchArticlesTool."""

    def test_credible_source_scores_high(self):
        tool = _make_tool()
        article = {
            'title': 'Test',
            'source': 'ESPN',
            'team': 'Cubs',
            'publishedAt': None,
        }
        scored = tool._score_article(article)
        assert scored['relevance_score'] > 0

    def test_unknown_source_scores_zero_credibility(self):
        tool = _make_tool()
        article = {
            'title': 'Test',
            'source': 'Random Blog',
            'team': 'Cubs',
            'publishedAt': None,
        }
        scored = tool._score_article(article)
        credible_article = {
            'title': 'Test',
            'source': 'ESPN',
            'team': 'Cubs',
            'publishedAt': None,
        }
        credible_scored = tool._score_article(credible_article)
        assert scored['relevance_score'] < credible_scored['relevance_score']

    def test_content_signal_keywords_boost_score(self):
        tool = _make_tool()
        with_signal = {
            'title': 'Cubs trade deadline moves',
            'source': 'X',
            'team': 'Cubs',
            'publishedAt': None,
        }
        without_signal = {
            'title': 'Cubs game today',
            'source': 'X',
            'team': 'Cubs',
            'publishedAt': None,
        }
        assert (
            tool._score_article(with_signal)['relevance_score']
            > tool._score_article(without_signal)['relevance_score']
        )

    def test_team_keyword_in_title_boosts_score(self):
        tool = _make_tool()
        with_team = {
            'title': 'Cubs win big',
            'source': 'X',
            'team': 'Cubs',
            'publishedAt': None,
        }
        without_team = {
            'title': 'Big win today',
            'source': 'X',
            'team': 'Cubs',
            'publishedAt': None,
        }
        assert (
            tool._score_article(with_team)['relevance_score']
            > tool._score_article(without_team)['relevance_score']
        )

    def test_trim_articles_respects_limit(self):
        config = {
            'collection': {'max_articles_per_source': 2},
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
        with (
            patch('tools.fetch_articles_tool.yaml.safe_load', return_value=config),
            patch('builtins.open'),
            patch('tools.fetch_articles_tool.NewsAPI_Collector'),
            patch('tools.fetch_articles_tool.SerpApiCollector'),
            patch('tools.fetch_articles_tool.Memory'),
        ):
            tool = FetchArticlesTool()
        articles = [{'relevance_score': i} for i in range(5)]
        trimmed = tool._trim_articles(articles)
        assert len(trimmed) == 2
        assert trimmed[0]['relevance_score'] == 4
