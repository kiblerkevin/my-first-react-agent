from pydantic import BaseModel, Field

class FetchArticlesInput(BaseModel):
    """Input schema for fetch_articles tool"""
    force_refresh: bool = Field(
        False,
        description="Whether to force refresh the articles data, bypassing any caches."
    )