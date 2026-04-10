
import requests
from datetime import datetime, timedelta

from utils.logger.logger import setup_logger
from constants.enums import ApiSource
from utils.article_collectors.api_collectors.api_collector import APICollector


logger = setup_logger(__name__)


API_SOURCE = ApiSource.NEWSAPI.value

NEWSAPI_QUERY = "(Chicago Bears OR Chicago Cubs OR Chicago White Sox OR Chicago Bulls OR Chicago Blackhawks OR Chicago Sky OR Chicago Fire FC OR Chicago Stars FC OR Chicago Hounds OR Chicago Wolves) -betting -odds -parlay -gambling -casino -picks -spread -lines -sportsbook"


class NewsAPI_Collector(APICollector):
    def __init__(self):
        super().__init__(API_SOURCE)

    def collect_articles(self):
        articles = []
        
        try:
            from_date = (datetime.now() - timedelta(hours=self.lookback_hours)).isoformat()
            
            params = {
                'q': self.config['apis'][API_SOURCE]['query'],
                'language': self.language,
                'sortBy': self.sort_by,
                'pageSize': self.page_size,
                'from': from_date,
                'apiKey': self.api_key
            }
            
            response = requests.get(self.url, params=params, timeout=self.timeout_seconds)
            response.raise_for_status()
            data = response.json()
            
            for item in data.get('articles', []):
                article = self._parse_article(item)
                if article:
                    articles.append(article)
                    
            logger.info(f"Collected {len(articles)} articles from NewsAPI.")
            
        except Exception as e:
            logger.error(f"Error occurred while collecting articles: {e}")

        return articles
    
    
    def _parse_article(self, item):
        if not item.get('content') or item.get('content') == 'Removed':
            content = item.get('description', '')
        else:
            content = item.get('content', '')
            
        if not content:
            return None
        
        return {
            'title': item.get('title'),
            'description': item.get('description'),
            'content': content,
            'url': item.get('url'),
            'publishedAt': item.get('publishedAt'),
            'source': item.get('source', {}).get('name')
        }