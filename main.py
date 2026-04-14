from utils.article_collectors.api_collectors.newsapi_collector import NewsAPI_Collector
from utils.article_collectors.api_collectors.serpapi_collector import SerpApiCollector
from utils.article_collectors.api_collectors.espn_collector import ESPNCollector

def main():

    articles = []

    # Collect articles from NewsAPI
    newsapi_collector = NewsAPI_Collector()
    newsapi_articles = newsapi_collector.collect_articles()
    articles.extend(newsapi_articles)

    # Collect articles from SerpApi
    serpapi_collector = SerpApiCollector()
    serpapi_articles = serpapi_collector.collect_articles()
    articles.extend(serpapi_articles)

    print(f"Total articles collected: {len(articles)}")
    for article in articles:
        print(f"Title: {article.get('title')}")
        print(f"URL: {article.get('url')}")
        print(f"Published At: {article.get('publishedAt')}")
        print("-" * 80)

    # Collect scores from ESPN
    espn_collector = ESPNCollector()
    scores = espn_collector.collect_articles()

    print(f"\nTotal scores collected: {len(scores)}")
    for score in scores:
        print(f"{score['away_team']} {score['away_score']} @ {score['home_team']} {score['home_score']} ({score['status']})")
        print("-" * 80)

if __name__ == "__main__":
    main()