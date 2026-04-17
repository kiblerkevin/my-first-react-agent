from pydantic import BaseModel, Field
from typing import Optional


class FetchScoresInput(BaseModel):
    """Input schema for fetch_scores tool"""
    force_refresh: bool = Field(
        False,
        description="Reserved for testing. Has no effect until the memory layer is active."
    )
    run_id: Optional[str] = Field(
        default=None,
        description="Workflow run ID for persisting API call results."
    )
