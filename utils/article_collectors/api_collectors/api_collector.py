"""Base class for API-based article collectors."""

import os
from typing import Any

import yaml
from dotenv import load_dotenv

config_path = 'config/sources.yaml'


class APICollector:
    """Base collector that loads API config and credentials from sources.yaml."""

    def __init__(self, api_value: str) -> None:
        """Initialize collector with config for the given API source.

        Args:
            api_value: Key in sources.yaml apis section (e.g. 'newsapi').
        """
        load_dotenv()

        with open(config_path, 'r') as file:
            self.config: dict[str, Any] = yaml.safe_load(file)
        env_key_name = self.config['apis'][api_value].get('env_key_name', None)
        self.api_key: str | None = os.getenv(env_key_name) if env_key_name else None
        self.language: str | None = self.config['apis'][api_value].get('language', None)
        self.lookback_hours: int = self.config['collection']['lookback_hours']
        self.page_size: int | None = self.config['apis'][api_value].get(
            'page_size', None
        )
        self.sort_by: str | None = self.config['apis'][api_value].get('sort_by', None)
        self.timeout_seconds: int = self.config['collection']['timeout_seconds']
        self.url: str = self.config['apis'][api_value]['url']

    def collect_articles(self) -> list[dict[str, Any]]:
        """Collect articles from the API. Override in subclasses."""
        return []
