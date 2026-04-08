import time

from tools.base_tool import BaseTool
from models.inputs.fetch_articles_input import FetchArticlesInput
from models.outputs.fetch_articles_output import FetchArticlesOutput
from utils.article_collectors.newsapi_collector import NewsApiCollector
from utils.article_collectors.serpapi_collector import SerpApiCollector
from utils.logger import setup_logger



logger = setup_logger(__name__)


class FetchArticlesTool(BaseTool):
    name = "fetch_articles"
    description = "Fetches the latest articles from configured sources. Can force refresh to bypass caches."
    input_schema = {
        "type": "object",
        "properties": {
            "force_refresh": {
                "type": "boolean",
                "description": "Whether to force refresh the articles data, bypassing any caches."
            }
        },
        "required": []
    }
    output_schema = {
        "type": "object",
        "properties": {
            "fetched_articles": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "url": {"type": "string"},
                        "published_at": {"type": "string", "format": "date-time"},
                        # Add other relevant article fields as needed
                    }
                },
                "description": "List of fetched articles with their details."
            }
        }
    }
    
    
    def __init__(self):
        super().__init__(
            name=self.name,
            description=self.description,
            input_schema=self.input_schema,
            output_schema=self.output_schema
        )
        self.article_collectors = {
            "newsapi": NewsApiCollector(),
            "serpapi": SerpApiCollector()
        }

    def execute(self, input: FetchArticlesInput) -> FetchArticlesOutput:
        # Implementation for fetching articles based on the input parameters
        # This is a placeholder and should be replaced with actual fetching logic
        force_refresh = input.force_refresh
        
        logger.info(f"Fetching articles with force_refresh={force_refresh}")
        start_time = time.time()
        
        article_output = FetchArticlesOutput()
        
        article_output = self._fetch_articles_from_sources(article_output)
        article_output = self._deduplicate_articles(article_output)
        article_output.article_count = len(article_output.articles)

        return article_output
    
    def _fetch_articles_from_sources(self, article_output):
        for source_name, collector in self.article_collectors.items():
            if collector.is_enabled():
                logger.info(f"Collecting articles from {source_name}...")
                articles = collector.collect_articles()
                article_output.articles.extend(articles)
                article_output.source_counts[source_name] = len(articles)
                logger.info(f"Collected {len(articles)} articles from {source_name}")
            else:
                logger.info(f"Source {source_name} is disabled in configuration.")
        
        return article_output
    
    def _deduplicate_articles(self, article_output):
        seen_urls = set()
        unique_articles = []

        for article in article_output.articles:
            url = article.get('url')
            if url not in seen_urls:
                seen_urls.add(url)
                unique_articles.append(article)

        article_output.articles = unique_articles
        return article_output
