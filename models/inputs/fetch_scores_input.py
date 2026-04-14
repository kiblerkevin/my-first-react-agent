from pydantic import BaseModel, Field


class FetchScoresInput(BaseModel):
    """Input schema for fetch_scores tool"""
    force_refresh: bool = Field(
        False,
        description="Reserved for testing. Has no effect until the memory layer is active."
    )
