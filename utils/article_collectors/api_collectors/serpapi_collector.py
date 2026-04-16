import serpapi
import time
from datetime import datetime, timezone, timedelta

import yaml

from utils.article_collectors.api_collectors.api_collector import APICollector
from utils.logger.logger import setup_logger
from constants.enums import ApiSource


logger = setup_logger(__name__)

API_SOURCE = ApiSource.SERPAPI.value
EXCLUSION_TERMS = "-betting -odds -gambling"
ORCHESTRATION_CONFIG_PATH = 'config/orchestration.yaml'


class SerpApiCollector(APICollector):
    def __init__(self):
        super().__init__(API_SOURCE)
        self.client = serpapi.Client(api_key=self.api_key)
        self.teams = self.config['teams']
        with open(ORCHESTRATION_CONFIG_PATH, 'r') as f:
            rl_config = yaml.safe_load(f).get('rate_limiting', {})
        self._rl_max_retries = rl_config.get('max_retries', 3)
        self._rl_base_delay = rl_config.get('base_delay_seconds', 1.0)

    def _search_with_retry(self, **kwargs) -> dict:
        for attempt in range(self._rl_max_retries + 1):
            try:
                return dict(self.client.search(**kwargs))
            except Exception as e:
                if '429' in str(e) and attempt < self._rl_max_retries:
                    delay = self._rl_base_delay * (2 ** attempt)
                    logger.warning(f"SerpAPI rate limited — retrying in {delay:.1f}s (attempt {attempt + 1}/{self._rl_max_retries})")
                    time.sleep(delay)
                else:
                    raise

    def collect_articles(self):
        seen_urls = set()
        articles = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.lookback_hours)

        for team in self.teams:
            try:
                search = self._search_with_retry(engine='google_news', q=f'"{team["name"]}" {EXCLUSION_TERMS}', tbs='qdr:d')
                results = search

                team_count = 0
                for item in results.get('sports_results', []) + results.get('news_results', []):
                    url = item.get('link')
                    if not url or url in seen_urls:
                        continue
                    iso_date = item.get('iso_date')
                    if iso_date and datetime.fromisoformat(iso_date.replace('Z', '+00:00')) < cutoff:
                        continue
                    seen_urls.add(url)
                    articles.append(self._parse_article(item, team['name']))
                    team_count += 1

                logger.info(f"Collected {team_count} articles for {team['name']} from SerpAPI.")

            except Exception as e:
                logger.error(f"Error collecting SerpAPI articles for {team['name']}: {e}")

        logger.info(f"Collected {len(articles)} total deduplicated articles from SerpAPI.")
        return articles

    def _parse_article(self, item, team):
        return {
            'title': item.get('title'),
            'url': item.get('link'),
            'publishedAt': item.get('iso_date'),
            'source': item.get('source', {}).get('name'),
            'team': team
        }