"""Mixin for article and summary persistence operations."""

import contextlib
import json as _json
from datetime import datetime, timedelta
from typing import Any

from memory.database import Article, ArticleSummary, get_session
from utils.logger.logger import setup_logger

logger = setup_logger(__name__)


class ArticlesMixin:
    """Article and article summary database operations."""

    def get_seen_urls(self) -> set[str]:
        """Get the set of URLs that have been seen."""
        session = get_session(self.engine)
        try:
            urls = session.query(Article.url).all()
            return {url for (url,) in urls}
        finally:
            session.close()

    def save_articles(self, articles: list[dict[str, Any]]) -> None:
        """Save a list of articles to the database."""
        session = get_session(self.engine)
        try:
            for article in articles:
                url = article.get('url')
                if not url:
                    continue
                existing = session.query(Article).filter_by(url=url).first()
                if existing:
                    continue
                published_at = None
                if article.get('publishedAt'):
                    with contextlib.suppress(Exception):
                        published_at = datetime.fromisoformat(
                            article['publishedAt'].replace('Z', '+00:00')
                        )
                session.add(
                    Article(
                        title=article.get('title', ''),
                        url=url,
                        source=article.get('source'),
                        team=article.get('team'),
                        published_at=published_at,
                    )
                )
            session.commit()
            logger.info(f'Saved {len(articles)} articles to memory.')
        finally:
            session.close()

    def purge_old_articles(self) -> None:
        """Purge articles older than the retention period."""
        session = get_session(self.engine)
        try:
            cutoff = datetime.utcnow() - timedelta(days=self.retention_days)
            count = session.query(Article).filter(Article.fetched_at < cutoff).delete()
            session.commit()
            if count:
                logger.info(
                    f'Purged {count} articles older than {self.retention_days} days.'
                )
        finally:
            session.close()

    def get_article_summary(self, url: str) -> dict[str, Any] | None:
        """Get the summary for an article by URL."""
        session = get_session(self.engine)
        try:
            s = session.query(ArticleSummary).filter_by(url=url).first()
            if not s:
                return None
            return {
                'url': s.url,
                'team': s.team,
                'summary': s.summary,
                'event_type': s.event_type,
                'players_mentioned': _json.loads(s.players_mentioned)
                if s.players_mentioned
                else [],
                'is_relevant': s.is_relevant,
            }
        finally:
            session.close()

    def save_article_summary(self, data: dict[str, Any]) -> None:
        """Save an article summary."""
        session = get_session(self.engine)
        try:
            existing = (
                session.query(ArticleSummary).filter_by(url=data.get('url')).first()
            )
            if existing:
                return
            session.add(
                ArticleSummary(
                    url=data.get('url', ''),
                    team=data.get('team'),
                    summary=data.get('summary', ''),
                    event_type=data.get('event_type'),
                    players_mentioned=_json.dumps(data.get('players_mentioned', [])),
                    is_relevant=data.get('is_relevant', True),
                )
            )
            session.commit()
            logger.info(f'Saved article summary for: {data.get("url", "")[:60]}')
        finally:
            session.close()
