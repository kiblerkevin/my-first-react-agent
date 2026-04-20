"""Tests for utils/consolidate.py."""

from utils.consolidate import consolidate_summaries


class TestConsolidateSummaries:
    """Tests for the consolidate_summaries function."""

    def test_merges_multiple_game_recaps_same_team(self):
        summaries = [
            {'team': 'Cubs', 'event_type': 'game_recap', 'summary': 'First recap.', 'players_mentioned': ['A', 'B']},
            {'team': 'Cubs', 'event_type': 'game_recap', 'summary': 'Second recap.', 'players_mentioned': ['B', 'C']},
        ]
        result = consolidate_summaries(summaries)
        recaps = [s for s in result if s['event_type'] == 'game_recap']
        assert len(recaps) == 1
        assert 'First recap.' in recaps[0]['summary']
        assert 'Second recap.' in recaps[0]['summary']
        assert recaps[0]['players_mentioned'] == ['A', 'B', 'C']

    def test_single_recap_passes_through(self):
        summaries = [
            {'team': 'Cubs', 'event_type': 'game_recap', 'summary': 'Only one.', 'players_mentioned': ['A']},
        ]
        result = consolidate_summaries(summaries)
        assert len(result) == 1
        assert result[0]['summary'] == 'Only one.'

    def test_non_game_summaries_kept_separate(self):
        summaries = [
            {'team': 'Cubs', 'event_type': 'trade', 'summary': 'Trade news.', 'players_mentioned': []},
            {'team': 'Cubs', 'event_type': 'injury', 'summary': 'Injury news.', 'players_mentioned': []},
        ]
        result = consolidate_summaries(summaries)
        assert len(result) == 2

    def test_mixed_event_types(self):
        summaries = [
            {'team': 'Cubs', 'event_type': 'game_recap', 'summary': 'Recap 1.', 'players_mentioned': ['A']},
            {'team': 'Cubs', 'event_type': 'game_recap', 'summary': 'Recap 2.', 'players_mentioned': ['B']},
            {'team': 'Cubs', 'event_type': 'trade', 'summary': 'Trade.', 'players_mentioned': ['C']},
        ]
        result = consolidate_summaries(summaries)
        assert len(result) == 2  # 1 merged recap + 1 trade

    def test_multiple_teams_independent(self):
        summaries = [
            {'team': 'Cubs', 'event_type': 'game_recap', 'summary': 'Cubs 1.', 'players_mentioned': []},
            {'team': 'Cubs', 'event_type': 'game_recap', 'summary': 'Cubs 2.', 'players_mentioned': []},
            {'team': 'Sox', 'event_type': 'game_recap', 'summary': 'Sox 1.', 'players_mentioned': []},
        ]
        result = consolidate_summaries(summaries)
        assert len(result) == 2  # 1 merged Cubs + 1 Sox

    def test_empty_input(self):
        assert consolidate_summaries([]) == []

    def test_deduplicates_players(self):
        summaries = [
            {'team': 'Cubs', 'event_type': 'game_recap', 'summary': 'A.', 'players_mentioned': ['X', 'Y']},
            {'team': 'Cubs', 'event_type': 'game_recap', 'summary': 'B.', 'players_mentioned': ['Y', 'Z']},
        ]
        result = consolidate_summaries(summaries)
        assert result[0]['players_mentioned'] == ['X', 'Y', 'Z']
