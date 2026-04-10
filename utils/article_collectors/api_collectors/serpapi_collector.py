from serpapi import GoogleSearch

from utils.article_collectors.api_collectors.api_collector import ApiCollector
from utils.logger.logger import setup_logger
from constants.enums import ApiSource


logger = setup_logger(__name__)


API_SOURCE = ApiSource.SERPAPI.value

SERPAPI_QUERY = '(Chicago Bears OR "Chicago Cubs" OR "Chicago White Sox" OR "Chicago Bulls" OR "Chicago Blackhawks" OR "Chicago Sky" OR "Chicago Fire FC" OR "Chicago Stars FC" OR "Chicago Hounds" OR "Chicago Wolves") -betting -odds -gambling'


class SerpApiCollector(ApiCollector):
    def __init__(self, config):
        super().__init__(API_SOURCE)

    def collect_articles(self):
        articles = []
        
        params = {
            "engine": "google_news",
            "api_key": self.api_key,
            "q": SERPAPI_QUERY,
            "gl": self.geolocation,
            "hl": self.language,
            "as_qdr": f"h{self.lookback_hours}",
        }
        
        try:
            search = GoogleSearch(params)
            results = search.get_dict()
            articles = results.get("sports_results", [])
            articles.extend(results.get("news_results", []))
            
            logger.info(f"Collected {len(articles)} articles from SerpAPI.")
        
        except Exception as e:
            logger.error(f"Error occurred while collecting articles from SerpAPI: {e}")
            
        return articles