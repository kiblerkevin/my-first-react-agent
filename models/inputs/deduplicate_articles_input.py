from pydantic import BaseModel, Field


class DeduplicateArticlesInput(BaseModel):
    """Input schema for deduplicate_articles tool."""

    articles: list[dict] = Field(
        default_factory=list,
        description="List of articles to deduplicate. Each article must have 'title', 'team', and 'url' fields.",
    )
    similarity_threshold: float = Field(
        default=85.0,
        description=(
            'Score from 0-100. Articles within the same team whose titles score at or above '
            'this threshold via fuzzy token_sort_ratio are considered duplicates. '
            'Higher values require closer title matches. Default 85 is recommended.'
        ),
    )
