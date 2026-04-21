"""Tool for publishing blog posts to WordPress.com via OAuth2 API."""

from typing import Any

import requests
from dotenv import load_dotenv

from memory.memory import Memory
from models.inputs.wordpress_publish_input import WordPressPublishInput
from models.outputs.wordpress_publish_output import WordPressPublishOutput
from tools.base_tool import BaseTool
from utils.http import rate_limited_request
from utils.logger.logger import setup_logger
from utils.secrets import get_secret

logger = setup_logger(__name__)

load_dotenv()

WP_API_BASE = 'https://public-api.wordpress.com/wp/v2/sites'


class WordPressPublishTool(BaseTool):
    """Publishes a blog post as a draft to WordPress.com via the REST API."""

    model_config = {'arbitrary_types_allowed': True, 'extra': 'allow'}

    input_model: type = WordPressPublishInput

    name: str = 'wordpress_publish'
    description: str = (
        'Publishes a blog post as a draft to WordPress.com. Resolves category and tag names '
        "to WordPress IDs (creating them via the API if they don't exist) and stores the "
        'resolved IDs in the local database for future use. Requires OAuth2 token — '
        'run /oauth/start on the approval server first to authorize.'
    )
    input_schema: dict[str, Any] = {
        'type': 'object',
        'properties': {
            'title': {'type': 'string'},
            'content': {'type': 'string'},
            'excerpt': {'type': 'string'},
            'categories': {'type': 'array', 'items': {'type': 'object'}},
            'tags': {'type': 'array', 'items': {'type': 'object'}},
        },
        'required': ['title', 'content'],
    }
    output_schema: dict[str, Any] = {
        'type': 'object',
        'properties': {
            'post_id': {'type': 'integer'},
            'post_url': {'type': 'string'},
            'status': {'type': 'string'},
            'categories_resolved': {'type': 'object'},
            'tags_resolved': {'type': 'object'},
            'error': {'type': 'string'},
        },
    }

    def __init__(self) -> None:
        """Initialize with WordPress site URL and memory layer."""
        super().__init__(
            name=self.model_fields['name'].default,
            description=self.model_fields['description'].default,
            input_schema=self.model_fields['input_schema'].default,
            output_schema=self.model_fields['output_schema'].default,
        )
        wp_url = (
            (get_secret('WORDPRESS_URL') or '')
            .replace('http://', '')
            .replace('https://', '')
        )
        self.site: str = wp_url
        self.base_url: str = f'{WP_API_BASE}/{wp_url}'
        self.memory = Memory()

    def _get_headers(self) -> dict[str, str]:
        """Get authorization headers using the stored OAuth token.

        Returns:
            Headers dict with Bearer token.

        Raises:
            RuntimeError: If no OAuth token is found.
        """
        token = self.memory.get_oauth_token('wordpress')
        if not token:
            raise RuntimeError(
                'No WordPress OAuth token found. '
                'Start the approval server and visit /oauth/start to authorize.'
            )
        return {'Authorization': f'Bearer {token}'}

    def _validate_token(self, headers: dict[str, str]) -> bool:
        """Validate the OAuth token against the WordPress API.

        Args:
            headers: Authorization headers to validate.

        Returns:
            True if token is valid, False otherwise.
        """
        try:
            response = requests.get(
                f'{self.base_url}/users/me',
                headers=headers,
                timeout=10,
            )
            if response.status_code == 200:
                return True
            logger.warning(f'OAuth token validation failed: {response.status_code}')
            return False
        except Exception as e:
            logger.warning(f'OAuth token validation error: {e}')
            return False

    def execute(self, input: WordPressPublishInput) -> WordPressPublishOutput:
        """Publish a blog post as a draft to WordPress.

        Args:
            input: Blog post title, content, excerpt, categories, and tags.

        Returns:
            Output with post ID, URL, status, and resolved taxonomy.
        """
        try:
            headers = self._get_headers()

            if not self._validate_token(headers):
                error_msg = (
                    'WordPress OAuth token is invalid or revoked. '
                    'Re-authorize by visiting /oauth/start on the approval server.'
                )
                logger.error(error_msg)
                return WordPressPublishOutput(error=error_msg)

            categories_resolved = self._resolve_categories(input.categories, headers)
            tags_resolved = self._resolve_tags(input.tags, headers)

            post_data: dict[str, Any] = {
                'title': input.title,
                'content': input.content,
                'excerpt': input.excerpt,
                'status': 'draft',
                'categories': list(categories_resolved.values()),
                'tags': list(tags_resolved.values()),
            }

            response = rate_limited_request(
                'POST',
                f'{self.base_url}/posts',
                json=post_data,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            output = WordPressPublishOutput(
                post_id=data.get('id', 0),
                post_url=data.get('link', ''),
                status=data.get('status', ''),
                categories_resolved=categories_resolved,
                tags_resolved=tags_resolved,
            )
            logger.info(
                f'Draft published: post_id={output.post_id}, url={output.post_url}'
            )
            return output

        except RuntimeError:
            raise
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code in (401, 403):
                error_msg = (
                    f'WordPress API returned {e.response.status_code} — token may be revoked. '
                    'Re-authorize by visiting /oauth/start on the approval server.'
                )
            else:
                error_msg = str(e)
            logger.error(f'Error publishing to WordPress: {error_msg}')
            return WordPressPublishOutput(error=error_msg)
        except Exception as e:
            logger.error(f'Error publishing to WordPress: {e}')
            return WordPressPublishOutput(error=str(e))

    def _resolve_categories(
        self, categories: list[dict[str, Any]], headers: dict[str, str]
    ) -> dict[str, int]:
        """Resolve category names to WordPress IDs, creating if needed.

        Args:
            categories: Category dicts with name and optional wordpress_id.
            headers: Authorization headers.

        Returns:
            Mapping of category name to WordPress ID.
        """
        resolved: dict[str, int] = {}
        for cat in categories:
            name = cat.get('name', '')
            wp_id = cat.get('wordpress_id')

            if wp_id:
                resolved[name] = wp_id
                continue

            wp_id = self._find_taxonomy('categories', name, headers)
            if not wp_id:
                wp_id = self._create_taxonomy('categories', name, headers)

            if wp_id:
                resolved[name] = wp_id
                self.memory.update_category_wordpress_id(name, wp_id)

        return resolved

    def _resolve_tags(
        self, tags: list[dict[str, Any]], headers: dict[str, str]
    ) -> dict[str, int]:
        """Resolve tag names to WordPress IDs, creating if needed.

        Args:
            tags: Tag dicts with name and optional wordpress_id.
            headers: Authorization headers.

        Returns:
            Mapping of tag name to WordPress ID.
        """
        resolved: dict[str, int] = {}
        for tag in tags:
            name = tag.get('name', '')
            wp_id = tag.get('wordpress_id')

            if wp_id:
                resolved[name] = wp_id
                continue

            wp_id = self._find_taxonomy('tags', name, headers)
            if not wp_id:
                wp_id = self._create_taxonomy('tags', name, headers)

            if wp_id:
                resolved[name] = wp_id
                self.memory.update_tag_wordpress_id(name, wp_id)

        return resolved

    def _find_taxonomy(
        self,
        taxonomy_type: str,
        name: str,
        headers: dict[str, str],
    ) -> int | None:
        """Search for an existing taxonomy item by name on WordPress.

        Args:
            taxonomy_type: 'categories' or 'tags'.
            name: Taxonomy name to search for.
            headers: Authorization headers.

        Returns:
            WordPress ID if found, None otherwise.
        """
        try:
            response = rate_limited_request(
                'GET',
                f'{self.base_url}/{taxonomy_type}',
                params={'search': name, 'per_page': 10},
                headers=headers,
                timeout=15,
            )
            response.raise_for_status()
            for item in response.json():
                if item.get('name', '').lower() == name.lower():
                    logger.info(
                        f'Found existing {taxonomy_type[:-1]}: {name} '
                        f'(wp_id={item["id"]})'
                    )
                    return item['id']
        except Exception as e:
            logger.warning(f"Error searching {taxonomy_type} for '{name}': {e}")
        return None

    def _create_taxonomy(
        self,
        taxonomy_type: str,
        name: str,
        headers: dict[str, str],
    ) -> int | None:
        """Create a new taxonomy item on WordPress.

        Args:
            taxonomy_type: 'categories' or 'tags'.
            name: Taxonomy name to create.
            headers: Authorization headers.

        Returns:
            WordPress ID of the created item, or None on failure.
        """
        try:
            response = rate_limited_request(
                'POST',
                f'{self.base_url}/{taxonomy_type}',
                json={'name': name},
                headers=headers,
                timeout=15,
            )
            response.raise_for_status()
            wp_id: int | None = response.json().get('id')
            logger.info(f'Created {taxonomy_type[:-1]}: {name} (wp_id={wp_id})')
            return wp_id
        except Exception as e:
            logger.warning(f"Error creating {taxonomy_type[:-1]} '{name}': {e}")
            return None
