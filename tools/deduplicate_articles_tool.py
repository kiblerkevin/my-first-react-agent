from collections import defaultdict

from rapidfuzz import fuzz

from tools.base_tool import BaseTool
from models.inputs.deduplicate_articles_input import DeduplicateArticlesInput
from models.outputs.deduplicate_articles_output import DeduplicateArticlesOutput
from utils.logger.logger import setup_logger


logger = setup_logger(__name__)


class DeduplicateArticlesTool(BaseTool):
    model_config = {"arbitrary_types_allowed": True, "extra": "allow"}

    input_model: type = DeduplicateArticlesInput

    name: str = "deduplicate_articles"
    description: str = (
        "Removes near-duplicate articles within each team using fuzzy title matching. "
        "Articles are pre-sorted by relevance_score so the highest-quality version of a "
        "duplicate pair is always retained. Call this tool after fetch_articles and before "
        "summarize_article to reduce redundant summarization calls."
    )
    input_schema: dict = {
        "type": "object",
        "properties": {
            "articles": {
                "type": "array",
                "description": "List of articles from fetch_articles to deduplicate.",
                "items": {"type": "object"}
            },
            "similarity_threshold": {
                "type": "number",
                "description": "Fuzzy match threshold 0-100. Default 85 is recommended."
            }
        },
        "required": ["articles"]
    }
    output_schema: dict = {
        "type": "object",
        "properties": {
            "unique_articles": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Deduplicated articles sorted by relevance_score descending."
            },
            "duplicate_count": {"type": "integer"},
            "duplicate_groups": {
                "type": "array",
                "items": {"type": "array", "items": {"type": "string"}},
                "description": "Groups of titles that were collapsed into one article."
            }
        }
    }

    def __init__(self):
        super().__init__(
            name=self.model_fields['name'].default,
            description=self.model_fields['description'].default,
            input_schema=self.model_fields['input_schema'].default,
            output_schema=self.model_fields['output_schema'].default
        )

    def execute(self, input: DeduplicateArticlesInput) -> DeduplicateArticlesOutput:
        threshold = input.similarity_threshold

        # Group by team and sort each group by relevance_score descending
        by_team = defaultdict(list)
        for article in input.articles:
            by_team[article.get('team', 'Unknown')].append(article)

        unique_articles = []
        duplicate_groups = []
        duplicate_count = 0

        for team, articles in by_team.items():
            sorted_articles = sorted(
                articles, key=lambda a: a.get('relevance_score', 0), reverse=True
            )

            accepted = []  # (article, title_lower) tuples for accepted articles
            groups = {}    # title -> list of duplicate titles collapsed into it

            for article in sorted_articles:
                title = article.get('title', '')
                title_lower = title.lower()
                matched_title = None

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
                f"{team}: {len(sorted_articles)} articles → "
                f"{len(team_unique)} unique, {len(sorted_articles) - len(team_unique)} duplicates removed."
            )

        logger.info(
            f"Deduplication complete: {len(unique_articles)} unique articles, "
            f"{duplicate_count} duplicates removed."
        )

        return DeduplicateArticlesOutput(
            unique_articles=unique_articles,
            duplicate_count=duplicate_count,
            duplicate_groups=duplicate_groups
        )
