"""Tests for tools/create_blog_taxonomy_tool.py."""

from unittest.mock import MagicMock, patch

from models.inputs.create_blog_taxonomy_input import CreateBlogTaxonomyInput
from tools.create_blog_taxonomy_tool import CreateBlogTaxonomyTool


class TestCreateBlogTaxonomyTool:
    """Tests for CreateBlogTaxonomyTool.execute."""

    @patch('tools.create_blog_taxonomy_tool.Memory')
    @patch('tools.create_blog_taxonomy_tool.yaml.safe_load')
    @patch('builtins.open')
    def test_assigns_default_category_plus_teams(
        self, mock_open, mock_yaml, mock_memory_cls
    ):
        mock_yaml.return_value = {
            'taxonomy': {'default_category': 'Daily Recap', 'max_player_tags': 4}
        }
        mock_memory = MagicMock()
        mock_memory.get_all_categories.return_value = []
        mock_memory.get_all_tags.return_value = []
        mock_memory.get_or_create_category.side_effect = lambda n: {
            'id': 1,
            'name': n,
            'wordpress_id': None,
        }
        mock_memory.get_or_create_tag.side_effect = lambda n: {
            'id': 1,
            'name': n,
            'wordpress_id': None,
        }
        mock_memory_cls.return_value = mock_memory

        tool = CreateBlogTaxonomyTool()
        result = tool.execute(
            CreateBlogTaxonomyInput(
                teams_covered=['Cubs', 'Sox'],
                players_mentioned=['A', 'B', 'A', 'C', 'D', 'E'],
            )
        )

        # Daily Recap + Cubs + Sox = 3 categories
        assert len(result.categories) == 3
        # Teams (Cubs, Sox) + top 4 players (A, B, C, D) = 6 tags
        assert len(result.tags) == 6

    @patch('tools.create_blog_taxonomy_tool.Memory')
    @patch('tools.create_blog_taxonomy_tool.yaml.safe_load')
    @patch('builtins.open')
    def test_tracks_new_categories(self, mock_open, mock_yaml, mock_memory_cls):
        mock_yaml.return_value = {
            'taxonomy': {'default_category': 'Daily Recap', 'max_player_tags': 4}
        }
        mock_memory = MagicMock()
        mock_memory.get_all_categories.return_value = [{'name': 'Daily Recap'}]
        mock_memory.get_all_tags.return_value = []
        mock_memory.get_or_create_category.side_effect = lambda n: {
            'id': 1,
            'name': n,
            'wordpress_id': None,
        }
        mock_memory.get_or_create_tag.side_effect = lambda n: {
            'id': 1,
            'name': n,
            'wordpress_id': None,
        }
        mock_memory_cls.return_value = mock_memory

        tool = CreateBlogTaxonomyTool()
        result = tool.execute(CreateBlogTaxonomyInput(teams_covered=['Cubs']))

        assert 'Cubs' in result.new_categories
        assert 'Daily Recap' not in result.new_categories
