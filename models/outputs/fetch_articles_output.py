from pydantic import BaseModel, Field


class FetchArticlesOutput(BaseModel):
    """Output schema for fetch_articles tool."""

    articles: list[dict] = Field(
        default_factory=list,
        description='List of collected sports articles, each with title, url, publishedAt, source, team, and relevance_score.',
    )
    article_count: int = Field(
        default=0,
        description='Total number of articles returned after deduplication, scoring, and trimming.',
    )
    source_counts: dict[str, int] = Field(
        default_factory=dict,
        description='Number of articles returned per source after trimming.',
    )
    errors: list[str] = Field(
        default_factory=list,
        description='Errors encountered per source during collection. Non-empty indicates partial results.',
    )
    new_articles: list[dict] = Field(
        default_factory=list,
        description='Articles not previously seen in memory. Populated once memory layer is active.',
    )
    new_article_count: int = Field(
        default=0,
        description='Number of new articles not previously seen. Populated once memory layer is active.',
    )
    filtered_article_count: int = Field(
        default=0,
        description='Number of articles filtered out by memory as previously seen. Populated once memory layer is active.',
    )
