from pydantic import BaseModel, Field


class SummarizeArticleOutput(BaseModel):
    """Output schema for summarize_article tool"""
    url: str = Field(default="", description="Echoed article URL for traceability.")
    team: str = Field(default="", description="Echoed Chicago team for traceability.")
    summary: str = Field(default="", description="2-3 sentence summary of the article's key facts.")
    event_type: str = Field(default="other", description="Type of event: game_recap, trade, injury, draft, roster, preview, opinion, or other.")
    players_mentioned: list[str] = Field(default_factory=list, description="Key players referenced in the article.")
    is_relevant: bool = Field(default=True, description="False if the article adds no value beyond score data or is off-topic.")
