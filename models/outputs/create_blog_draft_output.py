from pydantic import BaseModel, Field


class CreateBlogDraftOutput(BaseModel):
    """Output schema for create_blog_draft tool."""

    title: str = Field(
        default='',
        description="Blog post title, e.g. 'Chicago Sports Recap — April 14, 2026'.",
    )
    content: str = Field(
        default='',
        description='Full HTML blog post body following WordPress recommended styling.',
    )
    excerpt: str = Field(
        default='',
        description='1-2 sentence first-pass excerpt for SEO, to be refined by evaluate_blog_post.',
    )
    teams_covered: list[str] = Field(
        default_factory=list,
        description='Teams included in the post, for auditability.',
    )
    article_count: int = Field(
        default=0, description='Number of article summaries used in the draft.'
    )
