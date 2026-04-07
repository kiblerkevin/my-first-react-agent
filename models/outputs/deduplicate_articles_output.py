from pydantic import BaseModel, Field

class DeduplicateArticlesOutput(BaseModel):
    """Output schema for deduplicate_articles tool"""
    unique_articles: list[dict] = Field(description="List of unique articles after deduplication.")
    duplicate_count: int = Field(description="Number of duplicate articles removed.")