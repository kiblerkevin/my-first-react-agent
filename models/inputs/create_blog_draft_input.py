from pydantic import BaseModel, Field


class CreateBlogDraftInput(BaseModel):
    """Input schema for create_blog_draft tool"""
    summaries: list[dict] = Field(
        default_factory=list,
        description="List of article summaries from summarize_article, each with url, team, summary, event_type, players_mentioned, is_relevant."
    )
    scores: list[dict] = Field(
        default_factory=list,
        description="List of game scores from fetch_scores, each with team, date, status, completed, home_team, away_team, scores, records, headline, etc."
    )
