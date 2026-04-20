"""Tool for fetching and scoring Chicago sports articles from multiple APIs."""

from datetime import datetime, timezone
from typing import Any

import yaml

from memory.memory import Memory
from models.inputs.fetch_articles_input import FetchArticlesInput
from models.outputs.fetch_articles_output import FetchArticlesOutput
from tools.base_tool import BaseTool
from utils.article_collectors.api_collectors.newsapi_collector import (
    NewsAPI_Collector,
)
from utils.article_collectors.api_collectors.serpapi_collector import (
    SerpApiCollector,
)
from utils.logger.logger import setup_logger

logger = setup_logger(__name__)

CONFIG_PATH = 'config/sources.yaml'


class FetchArticlesTool(BaseTool):
    """Fetches, scores, trims, and deduplicates articles from NewsAPI and SerpAPI."""

    model_config = {'arbitrary_types_allowed': True, 'extra': 'allow'}
    input_model: type = FetchArticlesInput
    name: str = 'fetch_articles'
    description: str = (
        'Fetches the latest Chicago sports news articles from NewsAPI and SerpAPI for the past 24 hours. '
        'Returns a ranked list of articles (title, url, publishedAt, source, team, relevance_score) '
        'trimmed to the top 100 per source by relevance. Call this tool first before summarizing any articles.'
    )
    input_schema: dict[str, Any] = {
        'type': 'object',
        'properties': {
            'force_refresh': {
                'type': 'boolean',
                'description': (
                    'Reserved for testing. When true, the agent will re-process articles '
                    'regardless of prior memory. Has no effect until the memory layer is active.'
                ),
            }
        },
        'required': [],
    }
    output_schema: dict[str, Any] = {
        'type': 'object',
        'properties': {
            'articles': {
                'type': 'array',
                'description': 'Ranked list of articles after deduplication, scoring, and trimming.',
                'items': {
                    'type': 'object',
                    'properties': {
                        'title': {'type': 'string'},
                        'url': {'type': 'string'},
                        'publishedAt': {'type': 'string', 'format': 'date-time'},
                        'source': {'type': 'string'},
                        'team': {'type': 'string'},
                        'relevance_score': {'type': 'number'},
                    },
                },
            },
            'article_count': {'type': 'integer'},
            'source_counts': {'type': 'object'},
            'errors': {'type': 'array', 'items': {'type': 'string'}},
            'new_article_count': {'type': 'integer'},
            'filtered_article_count': {'type': 'integer'},
        },
    }

    def __init__(self) -> None:
        """Initialize with source config, collectors, and memory layer."""
        super().__init__(
            name=self.model_fields['name'].default,
            description=self.model_fields['description'].default,
            input_schema=self.model_fields['input_schema'].default,
            output_schema=self.model_fields['output_schema'].default,
        )
        with open(CONFIG_PATH, 'r') as f:
            self._config: dict[str, Any] = yaml.safe_load(f)

        self.max_articles_per_source: int = self._config['collection'][
            'max_articles_per_source'
        ]
        self.scoring_config: dict[str, Any] = self._config['relevance_scoring']
        self.article_collectors: dict[str, Any] = {
            'newsapi': NewsAPI_Collector(),
            'serpapi': SerpApiCollector(),
        }
        self.memory = Memory()

    def execute(self, input: FetchArticlesInput) -> FetchArticlesOutput:
        """Fetch, score, trim, and deduplicate articles from all sources.

        Args:
            input: Fetch options including force_refresh and run_id.

        Returns:
            Output with articles, counts, and memory filter results.
        """
        logger.info(f'Fetching articles (force_refresh={input.force_refresh})')

        output = FetchArticlesOutput()
        source_articles: dict[str, list[dict[str, Any]]] = {}

        for source_name, collector in self.article_collectors.items():
            try:
                articles = collector.collect_articles()
                scored = [self._score_article(a) for a in articles]
                trimmed = self._trim_articles(scored)
                source_articles[source_name] = trimmed
                output.source_counts[source_name] = len(trimmed)
                logger.info(
                    f'Retained {len(trimmed)} articles from {source_name} '
                    f'after scoring and trimming.'
                )
                if input.run_id:
                    db_id = self.memory.get_workflow_run_db_id(input.run_id)
                    if db_id:
                        self.memory.save_api_call_result(
                            db_id, source_name, 'success', len(trimmed)
                        )
            except Exception as e:
                error_msg = f'{source_name}: {e!s}'
                output.errors.append(error_msg)
                logger.error(f'Error collecting from {source_name}: {e}')
                if input.run_id:
                    db_id = self.memory.get_workflow_run_db_id(input.run_id)
                    if db_id:
                        self.memory.save_api_call_result(
                            db_id, source_name, 'error', error=str(e)
                        )

        all_articles = self._deduplicate_across_sources(source_articles)
        output.articles = all_articles
        output.article_count = len(all_articles)

        if input.force_refresh:
            output.new_articles = all_articles
            output.new_article_count = len(all_articles)
            output.filtered_article_count = 0
            logger.info('force_refresh=True — skipping memory filter.')
        else:
            seen_urls = self.memory.get_seen_urls()
            new_articles = [a for a in all_articles if a.get('url') not in seen_urls]
            output.new_articles = new_articles
            output.new_article_count = len(new_articles)
            output.filtered_article_count = len(all_articles) - len(new_articles)
            logger.info(
                f'Memory filter: {output.new_article_count} new, '
                f'{output.filtered_article_count} previously seen.'
            )

        self.memory.save_articles(output.new_articles)
        self.memory.purge_old_articles()

        return output

    def _score_article(self, article: dict[str, Any]) -> dict[str, Any]:
        """Calculate a relevance score for an article.

        Args:
            article: Article dict with title, source, team, publishedAt.

        Returns:
            Article dict with relevance_score added.
        """
        weights: dict[str, float] = self.scoring_config['weights']
        credible_sources = [s.lower() for s in self.scoring_config['credible_sources']]
        content_keywords = [
            k.lower() for k in self.scoring_config['content_signal_keywords']
        ]
        team_keywords = [article.get('team', '').lower()] if article.get('team') else []

        recency_score = self._score_recency(article.get('publishedAt'))
        credibility_score = (
            1.0 if (article.get('source') or '').lower() in credible_sources else 0.0
        )
        keyword_score = self._score_keyword_density(
            article.get('title', ''), team_keywords
        )
        content_score = self._score_content_signals(
            article.get('title', ''), content_keywords
        )

        total = (
            weights['recency'] * recency_score
            + weights['source_credibility'] * credibility_score
            + weights['team_keyword_density'] * keyword_score
            + weights['content_signals'] * content_score
        )

        article['relevance_score'] = round(total * 100, 2)
        return article

    def _score_recency(self, published_at: str | None) -> float:
        """Score article recency on a 0-1 scale (1 = just published).

        Args:
            published_at: ISO 8601 publish date string.

        Returns:
            Recency score between 0.0 and 1.0.
        """
        if not published_at:
            return 0.0
        try:
            pub_dt = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
            age_hours = (datetime.now(timezone.utc) - pub_dt).total_seconds() / 3600
            return max(0.0, 1.0 - (age_hours / 24))
        except Exception:
            return 0.0

    def _score_keyword_density(self, title: str, keywords: list[str]) -> float:
        """Score how many team keywords appear in the title.

        Args:
            title: Article title.
            keywords: Team-related keywords to match.

        Returns:
            Keyword density score between 0.0 and 1.0.
        """
        if not title or not keywords:
            return 0.0
        title_lower = title.lower()
        matches = sum(1 for kw in keywords if kw and kw in title_lower)
        return min(1.0, matches / len(keywords))

    def _score_content_signals(self, title: str, signal_keywords: list[str]) -> float:
        """Score presence of content signal keywords in the title.

        Args:
            title: Article title.
            signal_keywords: Content signal keywords to match.

        Returns:
            Content signal score between 0.0 and 1.0.
        """
        if not title:
            return 0.0
        title_lower = title.lower()
        matches = sum(1 for kw in signal_keywords if kw in title_lower)
        return min(1.0, matches / 3)

    def _trim_articles(self, articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Keep only the top N articles by relevance score.

        Args:
            articles: Scored articles.

        Returns:
            Top articles up to max_articles_per_source.
        """
        return sorted(
            articles,
            key=lambda a: a.get('relevance_score', 0),
            reverse=True,
        )[: self.max_articles_per_source]

    def _deduplicate_across_sources(
        self, source_articles: dict[str, list[dict[str, Any]]]
    ) -> list[dict[str, Any]]:
        """Remove duplicate URLs across sources.

        Args:
            source_articles: Articles grouped by source name.

        Returns:
            Deduplicated article list.
        """
        seen_urls: set[str] = set()
        unique: list[dict[str, Any]] = []
        for articles in source_articles.values():
            for article in articles:
                url = article.get('url')
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    unique.append(article)
        return unique
