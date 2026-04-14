import serpapi
from datetime import datetime, timezone, timedelta

from utils.article_collectors.api_collectors.api_collector import APICollector
from utils.logger.logger import setup_logger
from constants.enums import ApiSource


logger = setup_logger(__name__)

API_SOURCE = ApiSource.SERPAPI.value
EXCLUSION_TERMS = "-betting -odds -gambling"


class SerpApiCollector(APICollector):
    def __init__(self):
        super().__init__(API_SOURCE)
        self.client = serpapi.Client(api_key=self.api_key)
        self.teams = self.config['teams']

    def collect_articles(self):
        seen_urls = set()
        articles = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.lookback_hours)

        for team in self.teams:
            try:
                search = self.client.search(engine='google_news', q=f'"{team["name"]}" {EXCLUSION_TERMS}', tbs='qdr:d')
                results = dict(search)

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