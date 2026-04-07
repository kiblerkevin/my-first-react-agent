from pydantic import BaseModel, Field

class EvaluateBlogPostInput(BaseModel):
    """Input schema for evaluate_blog_post tool"""
    blog_post: dict = Field(description="The blog post to evaluate, including title, content, and metadata.")
    critieria: list[str] = Field(description="List of evaluation criteria to assess the blog post against, such as 'clarity', 'engagement', 'SEO', etc.")