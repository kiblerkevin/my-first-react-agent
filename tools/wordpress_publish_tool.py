import os

import requests
from dotenv import load_dotenv

from tools.base_tool import BaseTool
from models.inputs.wordpress_publish_input import WordPressPublishInput
from models.outputs.wordpress_publish_output import WordPressPublishOutput
from memory.memory import Memory
from utils.logger.logger import setup_logger


logger = setup_logger(__name__)

load_dotenv()

WP_API_BASE = "https://public-api.wordpress.com/wp/v2/sites"


class WordPressPublishTool(BaseTool):
    model_config = {"arbitrary_types_allowed": True, "extra": "allow"}

    input_model: type = WordPressPublishInput

    name: str = "wordpress_publish"
    description: str = (
        "Publishes a blog post as a draft to WordPress.com. Resolves category and tag names "
        "to WordPress IDs (creating them via the API if they don't exist) and stores the "
        "resolved IDs in the local database for future use. Requires OAuth2 token — "
        "run /oauth/start on the approval server first to authorize."
    )
    input_schema: dict = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "content": {"type": "string"},
            "excerpt": {"type": "string"},
            "categories": {"type": "array", "items": {"type": "object"}},
            "tags": {"type": "array", "items": {"type": "object"}}
        },
        "required": ["title", "content"]
    }
    output_schema: dict = {
        "type": "object",
        "properties": {
            "post_id": {"type": "integer"},
            "post_url": {"type": "string"},
            "status": {"type": "string"},
            "categories_resolved": {"type": "object"},
            "tags_resolved": {"type": "object"},
            "error": {"type": "string"}
        }
    }

    def __init__(self):
        super().__init__(
            name=self.model_fields['name'].default,
            description=self.model_fields['description'].default,
            input_schema=self.model_fields['input_schema'].default,
            output_schema=self.model_fields['output_schema'].default
        )
        wp_url = os.getenv('WORDPRESS_URL', '').replace('http://', '').replace('https://', '')
        self.site = wp_url
        self.base_url = f"{WP_API_BASE}/{wp_url}"
        self.memory = Memory()

    def _get_headers(self) -> dict:
        token = self.memory.get_oauth_token('wordpress')
        if not token:
            raise RuntimeError(
                "No WordPress OAuth token found. "
                "Start the approval server and visit /oauth/start to authorize."
            )
        return {'Authorization': f'Bearer {token}'}

    def execute(self, input: WordPressPublishInput) -> WordPressPublishOutput:
        try:
            headers = self._get_headers()
            categories_resolved = self._resolve_categories(input.categories, headers)
            tags_resolved = self._resolve_tags(input.tags, headers)

            post_data = {
                'title': input.title,
                'content': input.content,
                'excerpt': input.excerpt,
                'status': 'draft',
                'categories': list(categories_resolved.values()),
                'tags': list(tags_resolved.values())
            }

            response = requests.post(
                f"{self.base_url}/posts",
                json=post_data,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            output = WordPressPublishOutput(
                post_id=data.get('id', 0),
                post_url=data.get('link', ''),
                status=data.get('status', ''),
                categories_resolved=categories_resolved,
                tags_resolved=tags_resolved
            )
            logger.info(f"Draft published: post_id={output.post_id}, url={output.post_url}")
            return output

        except Exception as e:
            logger.error(f"Error publishing to WordPress: {e}")
            return WordPressPublishOutput(error=str(e))

    def _resolve_categories(self, categories: list[dict], headers: dict) -> dict[str, int]:
        resolved = {}
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

    def _resolve_tags(self, tags: list[dict], headers: dict) -> dict[str, int]:
        resolved = {}
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

    def _find_taxonomy(self, taxonomy_type: str, name: str, headers: dict) -> int | None:
        try:
            response = requests.get(
                f"{self.base_url}/{taxonomy_type}",
                params={'search': name, 'per_page': 10},
                headers=headers,
                timeout=15
            )
            response.raise_for_status()
            for item in response.json():
                if item.get('name', '').lower() == name.lower():
                    logger.info(f"Found existing {taxonomy_type[:-1]}: {name} (wp_id={item['id']})")
                    return item['id']
        except Exception as e:
            logger.warning(f"Error searching {taxonomy_type} for '{name}': {e}")
        return None

    def _create_taxonomy(self, taxonomy_type: str, name: str, headers: dict) -> int | None:
        try:
            response = requests.post(
                f"{self.base_url}/{taxonomy_type}",
                json={'name': name},
                headers=headers,
                timeout=15
            )
            response.raise_for_status()
            wp_id = response.json().get('id')
            logger.info(f"Created {taxonomy_type[:-1]}: {name} (wp_id={wp_id})")
            return wp_id
        except Exception as e:
            logger.warning(f"Error creating {taxonomy_type[:-1]} '{name}': {e}")
            return None
