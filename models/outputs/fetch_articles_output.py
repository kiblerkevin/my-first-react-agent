from pydantic import BaseModel, Field

class FetchArticlesOutput(BaseModel):
    """Output schema for fetch_articles tool"""
    articles: list[dict] = Field(description="List of collected sports article.")
    article_count: int = Field(description="Number of articles collected.")
    source_counts: dict[str, int] = Field(description="Counts of articles by source.")
    new_ReDoe.                       articles: list[dict] = Field(description="List of new articles collected since last fetch.")
    new_article_count: int = Field(description="Number of new articles collected since last fetch.")
    filtered_article_count: int = Field(description="Articles filtered by memory")