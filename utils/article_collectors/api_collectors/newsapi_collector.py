"""NewsAPI collector for Chicago sports articles."""

from datetime import datetime, timedelta
from typing import Any

from constants.enums import ApiSource
from utils.article_collectors.api_collectors.api_collector import APICollector
from utils.http import rate_limited_request
from utils.logger.logger import setup_logger

logger = setup_logger(__name__)

API_SOURCE = ApiSource.NEWSAPI.value
EXCLUSION_TERMS = '-betting -odds -gambling'


class NewsAPI_Collector(APICollector):
    """Collects articles per Chicago team from NewsAPI with deduplication."""

    def __init__(self) -> None:
        """Initialize with NewsAPI config and team list."""
        super().__init__(API_SOURCE)
        self.teams: list[dict[str, Any]] = self.config['teams']

    def collect_articles(self) -> list[dict[str, Any]]:
        """Fetch articles for each Chicago team from NewsAPI.

        Returns:
            Deduplicated list of article dicts across all teams.
        """
        seen_urls: set[str] = set()
        articles: list[dict[str, Any]] = []
        from_date = (datetime.now() - timedelta(hours=self.lookback_hours)).isoformat()

        for team in self.teams:
            try:
                params = {
                    'q': f'"{team["name"]}" {EXCLUSION_TERMS}',
                    'language': self.language,
                    'sortBy': self.sort_by,
                    'pageSize': self.page_size,
                    'from': from_date,
                    'apiKey': self.api_key,
                }

                response = rate_limited_request(
                    'GET', self.url, params=params, timeout=self.timeout_seconds
                )
                response.raise_for_status()
                data = response.json()

                team_count = 0
                for item in data.get('articles', []):
                    url = item.get('url')
                    if url in seen_urls:
                        continue
                    article = self._parse_article(item, team['name'])
                    if article:
                        seen_urls.add(url)
                        articles.append(article)
                        team_count += 1

                logger.info(
                    f'Collected {team_count} articles for {team["name"]} from NewsAPI.'
                )

            except Exception as e:
                logger.error(
                    f'Error collecting NewsAPI articles for {team["name"]}: {e}'
                )

        logger.info(
            f'Collected {len(articles)} total deduplicated articles from NewsAPI.'
        )
        return articles

    def _parse_article(self, item: dict[str, Any], team: str) -> dict[str, Any] | None:
        """Parse a NewsAPI article item into a standardized dict.

        Args:
            item: Raw article object from NewsAPI response.
            team: Chicago team name to tag on the article.

        Returns:
            Parsed article dict, or None if content is empty.
        """
        if not item.get('content') or item.get('content') == 'Removed':
            content = item.get('description', '')
        else:
            content = item.get('content', '')

        if not content:
            return None

        return {
            'title': item.get('title'),
            'url': item.get('url'),
            'publishedAt': item.get('publishedAt'),
            'source': item.get('source', {}).get('name'),
            'team': team,
        }
