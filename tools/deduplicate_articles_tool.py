"""Tool for fuzzy-matching deduplication of articles within each team."""

from collections import defaultdict
from typing import Any

from rapidfuzz import fuzz

from models.inputs.deduplicate_articles_input import DeduplicateArticlesInput
from models.outputs.deduplicate_articles_output import DeduplicateArticlesOutput
from tools.base_tool import BaseTool
from utils.logger.logger import setup_logger

logger = setup_logger(__name__)


class DeduplicateArticlesTool(BaseTool):
    """Removes near-duplicate articles within each team using fuzzy title matching."""

    model_config = {'arbitrary_types_allowed': True, 'extra': 'allow'}

    input_model: type = DeduplicateArticlesInput

    name: str = 'deduplicate_articles'
    description: str = (
        'Removes near-duplicate articles within each team using fuzzy title matching. '
        'Articles are pre-sorted by relevance_score so the highest-quality version of a '
        'duplicate pair is always retained. Call this tool after fetch_articles and before '
        'summarize_article to reduce redundant summarization calls.'
    )
    input_schema: dict[str, Any] = {
        'type': 'object',
        'properties': {
            'articles': {
                'type': 'array',
                'description': 'List of articles from fetch_articles to deduplicate.',
                'items': {'type': 'object'},
            },
            'similarity_threshold': {
                'type': 'number',
                'description': 'Fuzzy match threshold 0-100. Default 85 is recommended.',
            },
        },
        'required': ['articles'],
    }
    output_schema: dict[str, Any] = {
        'type': 'object',
        'properties': {
            'unique_articles': {
                'type': 'array',
                'items': {'type': 'object'},
                'description': 'Deduplicated articles sorted by relevance_score descending.',
            },
            'duplicate_count': {'type': 'integer'},
            'duplicate_groups': {
                'type': 'array',
                'items': {'type': 'array', 'items': {'type': 'string'}},
                'description': 'Groups of titles that were collapsed into one article.',
            },
        },
    }

    def __init__(self) -> None:
        """Initialize the deduplication tool."""
        super().__init__(
            name=self.model_fields['name'].default,
            description=self.model_fields['description'].default,
            input_schema=self.model_fields['input_schema'].default,
            output_schema=self.model_fields['output_schema'].default,
        )

    def execute(self, input: DeduplicateArticlesInput) -> DeduplicateArticlesOutput:
        """Deduplicate articles by fuzzy title matching within each team.

        Args:
            input: Articles and similarity threshold.

        Returns:
            Unique articles, duplicate count, and duplicate groups.
        """
        threshold = input.similarity_threshold

        by_team: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for article in input.articles:
            by_team[article.get('team', 'Unknown')].append(article)

        unique_articles: list[dict[str, Any]] = []
        duplicate_groups: list[list[str]] = []
        duplicate_count = 0

        for team, articles in by_team.items():
            sorted_articles = sorted(
                articles,
                key=lambda a: a.get('relevance_score', 0),
                reverse=True,
            )

            accepted: list[tuple[dict[str, Any], str]] = []
            groups: dict[str, list[str]] = {}

            for article in sorted_articles:
                title = article.get('title', '')
                title_lower = title.lower()
                matched_title: str | None = None

                for accepted_article, accepted_title in accepted:
                    score = fuzz.token_sort_ratio(title_lower, accepted_title)
                    if score >= threshold:
                        matched_title = accepted_article.get('title', '')
                        break

                if matched_title:
                    groups[matched_title].append(title)
                    duplicate_count += 1
                else:
                    accepted.append((article, title_lower))
                    groups[title] = []

            team_unique = [a for a, _ in accepted]
            unique_articles.extend(team_unique)

            for canonical_title, dupes in groups.items():
                if dupes:
                    duplicate_groups.append([canonical_title] + dupes)

            logger.info(
                f'{team}: {len(sorted_articles)} articles → '
                f'{len(team_unique)} unique, '
                f'{len(sorted_articles) - len(team_unique)} duplicates removed.'
            )

        logger.info(
            f'Deduplication complete: {len(unique_articles)} unique articles, '
            f'{duplicate_count} duplicates removed.'
        )

        return DeduplicateArticlesOutput(
            unique_articles=unique_articles,
            duplicate_count=duplicate_count,
            duplicate_groups=duplicate_groups,
        )
