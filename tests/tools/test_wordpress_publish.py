"""Tests for tools/wordpress_publish_tool.py."""

from unittest.mock import MagicMock, patch

from models.inputs.wordpress_publish_input import WordPressPublishInput
from tools.wordpress_publish_tool import WordPressPublishTool


def _make_tool():
    with patch('tools.wordpress_publish_tool.Memory') as mock_mem_cls, \
         patch.dict('os.environ', {'WORDPRESS_URL': 'test.wordpress.com'}):
        tool = WordPressPublishTool()
        tool.memory = mock_mem_cls.return_value
        return tool


class TestWordPressPublishTool:
    """Tests for WordPressPublishTool.execute."""

    def test_raises_on_missing_token(self):
        tool = _make_tool()
        tool.memory.get_oauth_token.return_value = None

        with pytest.raises(RuntimeError, match='No WordPress OAuth token'):
            tool.execute(WordPressPublishInput(title='Test', content='<p>Hi</p>'))

    @patch('tools.wordpress_publish_tool.rate_limited_request')
    @patch('tools.wordpress_publish_tool.requests.get')
    def test_returns_error_on_invalid_token(self, mock_get, mock_request):
        tool = _make_tool()
        tool.memory.get_oauth_token.return_value = 'bad_token'
        mock_get.return_value = MagicMock(status_code=401)

        result = tool.execute(WordPressPublishInput(title='Test', content='<p>Hi</p>'))

        assert result.error is not None
        assert 'invalid or revoked' in result.error

    @patch('tools.wordpress_publish_tool.rate_limited_request')
    @patch('tools.wordpress_publish_tool.requests.get')
    def test_publishes_draft_on_success(self, mock_get, mock_request):
        tool = _make_tool()
        tool.memory.get_oauth_token.return_value = 'valid_token'
        mock_get.return_value = MagicMock(status_code=200)

        mock_response = MagicMock(status_code=201)
        mock_response.json.return_value = {'id': 42, 'link': 'https://test.wordpress.com/p/42', 'status': 'draft'}
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        result = tool.execute(WordPressPublishInput(
            title='Test Post', content='<p>Content</p>', excerpt='Excerpt',
            categories=[{'name': 'Daily Recap', 'wordpress_id': 5}],
            tags=[{'name': 'Cubs', 'wordpress_id': 10}],
        ))

        assert result.post_id == 42
        assert result.status == 'draft'
        assert result.error is None
        assert result.categories_resolved == {'Daily Recap': 5}
        assert result.tags_resolved == {'Cubs': 10}

    @patch('tools.wordpress_publish_tool.rate_limited_request')
    @patch('tools.wordpress_publish_tool.requests.get')
    def test_resolves_categories_via_api(self, mock_get, mock_request):
        tool = _make_tool()
        tool.memory.get_oauth_token.return_value = 'valid_token'
        mock_get.return_value = MagicMock(status_code=200)

        # First call: search returns empty, second: create returns id
        search_response = MagicMock(status_code=200)
        search_response.json.return_value = []
        search_response.raise_for_status = MagicMock()

        create_response = MagicMock(status_code=201)
        create_response.json.return_value = {'id': 99}
        create_response.raise_for_status = MagicMock()

        post_response = MagicMock(status_code=201)
        post_response.json.return_value = {'id': 1, 'link': 'http://x', 'status': 'draft'}
        post_response.raise_for_status = MagicMock()

        mock_request.side_effect = [search_response, create_response, post_response]

        result = tool.execute(WordPressPublishInput(
            title='Test', content='<p>X</p>',
            categories=[{'name': 'New Cat'}], tags=[],
        ))

        assert result.categories_resolved == {'New Cat': 99}
        tool.memory.update_category_wordpress_id.assert_called_with('New Cat', 99)

    @patch('tools.wordpress_publish_tool.rate_limited_request')
    @patch('tools.wordpress_publish_tool.requests.get')
    def test_handles_http_error(self, mock_get, mock_request):
        import requests
        tool = _make_tool()
        tool.memory.get_oauth_token.return_value = 'valid_token'
        mock_get.return_value = MagicMock(status_code=200)

        error_response = MagicMock(status_code=500)
        error_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=error_response)
        mock_request.return_value = error_response

        result = tool.execute(WordPressPublishInput(
            title='Test', content='<p>X</p>', categories=[], tags=[],
        ))

        assert result.error is not None


import pytest


class TestWordPressPublishToolEdgeCases:
    """Tests for WordPress publish edge cases and tag resolution."""

    @patch('tools.wordpress_publish_tool.rate_limited_request')
    @patch('tools.wordpress_publish_tool.requests.get')
    def test_resolves_tags_via_api_search(self, mock_get, mock_request):
        tool = _make_tool()
        tool.memory.get_oauth_token.return_value = 'valid_token'
        mock_get.return_value = MagicMock(status_code=200)

        # Search finds existing tag
        search_response = MagicMock(status_code=200)
        search_response.json.return_value = [{'id': 55, 'name': 'Cubs'}]
        search_response.raise_for_status = MagicMock()

        post_response = MagicMock(status_code=201)
        post_response.json.return_value = {'id': 1, 'link': 'http://x', 'status': 'draft'}
        post_response.raise_for_status = MagicMock()

        mock_request.side_effect = [search_response, post_response]

        result = tool.execute(WordPressPublishInput(
            title='Test', content='<p>X</p>',
            categories=[], tags=[{'name': 'Cubs'}],
        ))

        assert result.tags_resolved == {'Cubs': 55}
        tool.memory.update_tag_wordpress_id.assert_called_with('Cubs', 55)

    @patch('tools.wordpress_publish_tool.rate_limited_request')
    @patch('tools.wordpress_publish_tool.requests.get')
    def test_creates_tag_when_not_found(self, mock_get, mock_request):
        tool = _make_tool()
        tool.memory.get_oauth_token.return_value = 'valid_token'
        mock_get.return_value = MagicMock(status_code=200)

        # Search returns empty, create returns new id
        search_response = MagicMock(status_code=200)
        search_response.json.return_value = []
        search_response.raise_for_status = MagicMock()

        create_response = MagicMock(status_code=201)
        create_response.json.return_value = {'id': 77}
        create_response.raise_for_status = MagicMock()

        post_response = MagicMock(status_code=201)
        post_response.json.return_value = {'id': 1, 'link': 'http://x', 'status': 'draft'}
        post_response.raise_for_status = MagicMock()

        mock_request.side_effect = [search_response, create_response, post_response]

        result = tool.execute(WordPressPublishInput(
            title='Test', content='<p>X</p>',
            categories=[], tags=[{'name': 'NewTag'}],
        ))

        assert result.tags_resolved == {'NewTag': 77}

    @patch('tools.wordpress_publish_tool.rate_limited_request')
    @patch('tools.wordpress_publish_tool.requests.get')
    def test_handles_token_validation_exception(self, mock_get, mock_request):
        tool = _make_tool()
        tool.memory.get_oauth_token.return_value = 'valid_token'
        mock_get.side_effect = Exception('Network error')

        result = tool.execute(WordPressPublishInput(title='Test', content='<p>X</p>'))

        assert result.error is not None
        assert 'invalid or revoked' in result.error

    @patch('tools.wordpress_publish_tool.rate_limited_request')
    @patch('tools.wordpress_publish_tool.requests.get')
    def test_handles_401_http_error(self, mock_get, mock_request):
        import requests as req
        tool = _make_tool()
        tool.memory.get_oauth_token.return_value = 'valid_token'
        mock_get.return_value = MagicMock(status_code=200)

        error_response = MagicMock(status_code=401)
        http_error = req.exceptions.HTTPError(response=error_response)
        mock_request.return_value = MagicMock(
            raise_for_status=MagicMock(side_effect=http_error),
            status_code=401,
        )

        result = tool.execute(WordPressPublishInput(
            title='Test', content='<p>X</p>', categories=[], tags=[],
        ))

        assert 'token may be revoked' in result.error

    @patch('tools.wordpress_publish_tool.rate_limited_request')
    @patch('tools.wordpress_publish_tool.requests.get')
    def test_handles_generic_exception(self, mock_get, mock_request):
        tool = _make_tool()
        tool.memory.get_oauth_token.return_value = 'valid_token'
        mock_get.return_value = MagicMock(status_code=200)
        mock_request.side_effect = ConnectionError('Network failed')

        result = tool.execute(WordPressPublishInput(
            title='Test', content='<p>X</p>', categories=[], tags=[],
        ))
        assert result.error is not None
        assert 'Network failed' in result.error

    @patch('tools.wordpress_publish_tool.rate_limited_request')
    @patch('tools.wordpress_publish_tool.requests.get')
    def test_find_taxonomy_error_returns_none(self, mock_get, mock_request):
        tool = _make_tool()
        tool.memory.get_oauth_token.return_value = 'valid_token'
        headers = {'Authorization': 'Bearer valid_token'}

        mock_request.side_effect = Exception('Search failed')
        result = tool._find_taxonomy('categories', 'Test', headers)
        assert result is None

    @patch('tools.wordpress_publish_tool.rate_limited_request')
    @patch('tools.wordpress_publish_tool.requests.get')
    def test_create_taxonomy_error_returns_none(self, mock_get, mock_request):
        tool = _make_tool()
        tool.memory.get_oauth_token.return_value = 'valid_token'
        headers = {'Authorization': 'Bearer valid_token'}

        mock_request.side_effect = Exception('Create failed')
        result = tool._create_taxonomy('tags', 'Test', headers)
        assert result is None
