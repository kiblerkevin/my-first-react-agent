from pydantic import BaseModel, Field


class SendApprovalEmailInput(BaseModel):
    """Input schema for send_approval_email tool."""

    title: str = Field(description='Blog post title.')
    content: str = Field(description='Full HTML blog post body.')
    excerpt: str = Field(default='', description='SEO excerpt.')
    categories: list[dict] = Field(
        default_factory=list, description='Assigned categories from taxonomy tool.'
    )
    tags: list[dict] = Field(
        default_factory=list, description='Assigned tags from taxonomy tool.'
    )
    evaluation_scores: dict = Field(
        default_factory=dict, description='Criteria scores from evaluate_blog_post.'
    )
    summaries: list[dict] = Field(
        default_factory=list, description='Article summaries used in the draft.'
    )
    scores: list[dict] = Field(
        default_factory=list, description='Game scores used in the draft.'
    )
