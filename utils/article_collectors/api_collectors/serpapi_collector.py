import serpapi

from utils.article_collectors.api_collectors.api_collector import APICollector
from utils.logger.logger import setup_logger
from constants.enums import ApiSource


logger = setup_logger(__name__)


API_SOURCE = ApiSource.SERPAPI.value

SERPAPI_QUERY = '(Chicago Bears OR "Chicago Cubs" OR "Chicago White Sox" OR "Chicago Bulls" OR "Chicago Blackhawks" OR "Chicago Sky" OR "Chicago Fire FC" OR "Chicago Stars FC" OR "Chicago Hounds" OR "Chicago Wolves") -betting -odds -gambling'


class SerpApiCollector(APICollector):
    def __init__(self):
        super().__init__(API_SOURCE)
        self.client = serpapi.Client(api_key=self.api_key)

    def collect_articles(self):
        articles = []
        
        params = {
            "engine": "google_news",
            "q": SERPAPI_QUERY,
            "hl": self.language,
        }
        
        try:
            search = self.client.search(**params)
            results = search.get_dict()
            articles = results.get("sports_results", [])
            articles.extend(results.get("news_results", []))
            
            logger.info(f"Collected {len(articles)} articles from SerpAPI.")
        
        except Exception as e:
            logger.error(f"Error occurred while collecting articles from SerpAPI: {e}")
            
        return articles