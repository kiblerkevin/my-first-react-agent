"""Lambda handler: Fetch articles from NewsAPI and SerpAPI."""

from src.shared.config import MAX_ARTICLES_PER_SOURCE, SCORING_WEIGHTS, CREDIBLE_SOURCES, CONTENT_SIGNAL_KEYWORDS
from src.shared.dynamo_memory import DynamoMemory
from src.shared.secrets import get_secret
from utils.article_collectors.api_collectors.newsapi_collector import NewsAPI_Collector
from utils.article_collectors.api_collectors.serpapi_collector import SerpApiCollector
from datetime import datetime, timezone

memory = DynamoMemory()


def handler(event, context):
    run_id = event.get("run_id")

    collectors = {"newsapi": NewsAPI_Collector(), "serpapi": SerpApiCollector()}
    source_articles: dict[str, list] = {}
    errors = []

    for source_name, collector in collectors.items():
        try:
            articles = collector.collect_articles()
            scored = [_score_article(a) for a in articles]
            trimmed = sorted(scored, key=lambda a: a.get("relevance_score", 0), reverse=True)[:MAX_ARTICLES_PER_SOURCE]
            source_articles[source_name] = trimmed
            memory.save_api_call_result(run_id, source_name, "success", len(trimmed))
        except Exception as e:
            errors.append(f"{source_name}: {e}")
            memory.save_api_call_result(run_id, source_name, "error", error=str(e))

    # Deduplicate across sources
    seen_urls: set[str] = set()
    all_articles = []
    for articles in source_articles.values():
        for article in articles:
            url = article.get("url")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_articles.append(article)

    # Filter against previously seen
    existing_urls = memory.get_seen_urls()
    new_articles = [a for a in all_articles if a.get("url") not in existing_urls]

    memory.save_articles(new_articles)
    memory.save_checkpoint(run_id, "fetch_articles", {
        "articles": all_articles,
        "new_articles": new_articles,
        "article_count": len(all_articles),
        "new_article_count": len(new_articles),
    })

    return {
        "article_count": len(all_articles),
        "new_article_count": len(new_articles),
    }


def _score_article(article: dict) -> dict:
    recency = _score_recency(article.get("publishedAt"))
    credibility = 1.0 if (article.get("source") or "").lower() in [s.lower() for s in CREDIBLE_SOURCES] else 0.0
    team_kw = [article.get("team", "").lower()] if article.get("team") else []
    keyword = _score_keywords(article.get("title", ""), team_kw)
    content = _score_content(article.get("title", ""))

    total = (
        SCORING_WEIGHTS["recency"] * recency
        + SCORING_WEIGHTS["source_credibility"] * credibility
        + SCORING_WEIGHTS["team_keyword_density"] * keyword
        + SCORING_WEIGHTS["content_signals"] * content
    )
    article["relevance_score"] = round(total * 100, 2)
    return article


def _score_recency(published_at: str | None) -> float:
    if not published_at:
        return 0.0
    try:
        pub_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - pub_dt).total_seconds() / 3600
        return max(0.0, 1.0 - (age_hours / 24))
    except Exception:
        return 0.0


def _score_keywords(title: str, keywords: list[str]) -> float:
    if not title or not keywords:
        return 0.0
    title_lower = title.lower()
    matches = sum(1 for kw in keywords if kw and kw in title_lower)
    return min(1.0, matches / len(keywords))


def _score_content(title: str) -> float:
    if not title:
        return 0.0
    title_lower = title.lower()
    matches = sum(1 for kw in CONTENT_SIGNAL_KEYWORDS if kw in title_lower)
    return min(1.0, matches / 3)
