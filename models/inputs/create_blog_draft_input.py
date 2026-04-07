from pydantic import BaseModel, Field

class GenerateBlogPostInput(BaseModel):
    """Input schema for generate_blog_post tool"""
    topic: str = Field(description="The topic for the blog post.")
    target_audience: str = Field(description="The target audience for the blog post.")
    desired_length: int = Field(description="The desired length of the blog post in words.")