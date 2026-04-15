from pydantic import BaseModel, Field


class DeduplicateArticlesOutput(BaseModel):
    """Output schema for deduplicate_articles tool"""
    unique_articles: list[dict] = Field(
        default_factory=list,
        description="List of unique articles after deduplication, sorted by relevance_score descending."
    )
    duplicate_count: int = Field(
        default=0,
        description="Number of duplicate articles removed."
    )
    duplicate_groups: list[list[str]] = Field(
        default_factory=list,
        description="Each inner list contains the titles of articles collapsed into one. For auditability."
    )
