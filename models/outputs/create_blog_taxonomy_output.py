from pydantic import BaseModel, Field

class CreateBlogTaxonomyOutput(BaseModel):
    """Output schema for create_blog_taxonomy tool"""
    assigned_category: str = Field(description="The category assigned to the blog post.")
    assigned_tags: list[str] = Field(description="List of tags assigned to the blog post.")
    new_categories: list[str] = Field(description="List of any new categories that were created to classify the blog post.")
    new_tags: list[str] = Field(description="List of any new tags that were created to assign to the blog post.")