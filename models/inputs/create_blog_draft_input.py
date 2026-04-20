from typing import Optional

from pydantic import BaseModel, Field


class CreateBlogDraftInput(BaseModel):
    """Input schema for create_blog_draft tool."""

    summaries: list[dict] = Field(
        default_factory=list,
        description='List of article summaries from summarize_article, each with url, team, summary, event_type, players_mentioned, is_relevant.',
    )
    scores: list[dict] = Field(
        default_factory=list,
        description='List of game scores from fetch_scores, each with team, date, status, completed, home_team, away_team, scores, records, headline, etc.',
    )
    current_draft: Optional[str] = Field(
        default=None,
        description='Existing HTML draft to revise. When provided alongside revision_notes, the model revises rather than rewrites from scratch.',
    )
    revision_notes: Optional[dict] = Field(
        default=None,
        description='Per-criterion improvement suggestions from evaluate_blog_post to address in the revision.',
    )
    rejection_feedback: Optional[str] = Field(
        default=None,
        description='Feedback from the most recent human rejection. The drafter should address this feedback.',
    )
