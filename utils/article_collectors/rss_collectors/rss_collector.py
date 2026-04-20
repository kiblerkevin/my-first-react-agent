"""Base class for RSS feed collectors."""

from typing import Any

import yaml

config_path = 'config/sources.yaml'


class RssCollector:
    """Base RSS feed collector. Subclass and override collect_articles."""

    def __init__(self, rss_value: str) -> None:
        """Initialize with config for the given RSS source.

        Args:
            rss_value: Key in sources.yaml apis section.
        """
        with open(config_path, 'r') as f:
            self.config: dict[str, Any] = yaml.safe_load(f)
        self.lookback_hours: int = self.config['collection']['lookback_hours']
        self.timeout_seconds: int = self.config['collection']['timeout_seconds']
        self.url: str = self.config['apis'][rss_value]['url']

    def collect_articles(self) -> list[dict[str, Any]]:
        """Collect articles from the RSS feed. Override in subclasses."""
        return []
