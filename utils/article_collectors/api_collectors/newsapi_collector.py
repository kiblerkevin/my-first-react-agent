
import requests
from datetime import datetime, timedelta

from utils.logger.logger import setup_logger
from constants.enums import ApiSource
from utils.article_collectors.api_collectors.api_collector import APICollector


logger = setup_logger(__name__)


API_SOURCE = ApiSource.NEWSAPI.value
EXCLUSION_TERMS = "-betting -odds -gambling"


class NewsAPI_Collector(APICollector):
    def __init__(self):
        super().__init__(API_SOURCE)
        self.teams = self.config['teams']

    def collect_articles(self):
        seen_urls = set()
        articles = []
        from_date = (datetime.now() - timedelta(hours=self.lookback_hours)).isoformat()

        for team in self.teams:
            try:
                params = {
                    'q': f'"{team["name"]}" {EXCLUSION_TERMS}',
                    'language': self.language,
                    'sortBy': self.sort_by,
                    'pageSize': self.page_size,
                    'from': from_date,
                    'apiKey': self.api_key
                }

                response = requests.get(self.url, params=params, timeout=self.timeout_seconds)
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

                logger.info(f"Collected {team_count} articles for {team['name']} from NewsAPI.")

            except Exception as e:
                logger.error(f"Error collecting NewsAPI articles for {team['name']}: {e}")

        logger.info(f"Collected {len(articles)} total deduplicated articles from NewsAPI.")
        return articles
    
    
    def _parse_article(self, item, team):
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
            'team': team
        }