from pydantic import BaseModel, Field

class DeduplicateArticlesInput(BaseModel):
    """Input schema for deduplicate_articles tool"""
    articles: list[dict] = Field(description="List of articles to deduplicate.")
    similarity_threshold: float = Field(description="Threshold for considering two articles as duplicates, between 0 and 1.")