from pydantic import BaseModel, Field


class FetchScoresOutput(BaseModel):
    """Output schema for fetch_scores tool"""
    scores: list[dict] = Field(
        default_factory=list,
        description=(
            "List of Chicago team game scores. Each entry includes: team, game_id, date, "
            "season_type, status, status_detail, completed, home_team, away_team, home_score, "
            "away_score, home_record, away_record, home_hits, away_hits, home_errors, "
            "away_errors, venue, neutral_site, headline, short_link_text, game_url."
        )
    )
    score_count: int = Field(default=0, description="Total number of games returned.")
    errors: list[str] = Field(
        default_factory=list,
        description="Collection errors per team, if any. Non-empty indicates partial results."
    )
