from pydantic import BaseModel, Field
from typing import Optional

class FetchArticlesInput(BaseModel):
    """Input schema for fetch_articles tool"""
    force_refresh: bool = Field(
        False,
        description="Whether to force refresh the articles data, bypassing any caches."
    )
    run_id: Optional[str] = Field(
        default=None,
        description="Workflow run ID for persisting API call results."
    )