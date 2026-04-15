from pydantic import BaseModel, Field


class EvaluateBlogPostInput(BaseModel):
    """Input schema for evaluate_blog_post tool"""
    title: str = Field(default="", description="Blog post title from create_blog_draft.")
    content: str = Field(default="", description="Full HTML blog post body from create_blog_draft.")
    excerpt: str = Field(default="", description="First-pass excerpt from create_blog_draft.")
    summaries: list[dict] = Field(
        default_factory=list,
        description="Article summaries from summarize_article used as ground truth for accuracy scoring."
    )
    scores: list[dict] = Field(
        default_factory=list,
        description="Game scores from fetch_scores used as ground truth for completeness scoring."
    )
