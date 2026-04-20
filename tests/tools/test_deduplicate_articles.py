"""Tests for tools/deduplicate_articles_tool.py."""

from models.inputs.deduplicate_articles_input import DeduplicateArticlesInput
from tools.deduplicate_articles_tool import DeduplicateArticlesTool


class TestDeduplicateArticlesTool:
    """Tests for DeduplicateArticlesTool.execute."""

    def setup_method(self):
        self.tool = DeduplicateArticlesTool()

    def test_removes_fuzzy_duplicates_same_team(self):
        articles = [
            {'title': 'Cubs rally in 7th to beat Brewers', 'team': 'Cubs', 'url': 'a', 'relevance_score': 90},
            {'title': 'Cubs rally in the 7th inning to beat Brewers', 'team': 'Cubs', 'url': 'b', 'relevance_score': 80},
        ]
        result = self.tool.execute(DeduplicateArticlesInput(articles=articles))
        assert len(result.unique_articles) == 1
        assert result.duplicate_count == 1
        assert result.unique_articles[0]['url'] == 'a'  # higher score retained

    def test_keeps_different_articles(self):
        articles = [
            {'title': 'Cubs win game', 'team': 'Cubs', 'url': 'a', 'relevance_score': 90},
            {'title': 'White Sox lose badly', 'team': 'Cubs', 'url': 'b', 'relevance_score': 80},
        ]
        result = self.tool.execute(DeduplicateArticlesInput(articles=articles))
        assert len(result.unique_articles) == 2
        assert result.duplicate_count == 0

    def test_deduplicates_within_team_only(self):
        articles = [
            {'title': 'Team wins big game today', 'team': 'Cubs', 'url': 'a', 'relevance_score': 90},
            {'title': 'Team wins big game today', 'team': 'Sox', 'url': 'b', 'relevance_score': 80},
        ]
        result = self.tool.execute(DeduplicateArticlesInput(articles=articles))
        assert len(result.unique_articles) == 2  # same title, different teams

    def test_custom_threshold(self):
        articles = [
            {'title': 'Cubs win', 'team': 'Cubs', 'url': 'a', 'relevance_score': 90},
            {'title': 'Cubs won', 'team': 'Cubs', 'url': 'b', 'relevance_score': 80},
        ]
        # Very low threshold should match almost anything
        result = self.tool.execute(DeduplicateArticlesInput(articles=articles, similarity_threshold=50.0))
        assert len(result.unique_articles) == 1

    def test_empty_input(self):
        result = self.tool.execute(DeduplicateArticlesInput(articles=[]))
        assert result.unique_articles == []
        assert result.duplicate_count == 0

    def test_duplicate_groups_reported(self):
        articles = [
            {'title': 'Cubs rally in 7th to beat Brewers', 'team': 'Cubs', 'url': 'a', 'relevance_score': 90},
            {'title': 'Cubs rally in the 7th inning to beat Brewers', 'team': 'Cubs', 'url': 'b', 'relevance_score': 80},
        ]
        result = self.tool.execute(DeduplicateArticlesInput(articles=articles))
        assert len(result.duplicate_groups) == 1
        assert len(result.duplicate_groups[0]) == 2  # canonical + 1 dupe
