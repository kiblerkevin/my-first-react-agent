from pydantic import BaseModel, Field

class CreateBlogTaxonomyInput(BaseModel):
    blog_post: dict = Field(description="The blog post for which to create the taxonomy.")
    previously_used_categories: list[str] = Field(description="List of previously used categories to classify the blog post into.")
    previously_used_tags: list[str] = Field(description="List of previously used tags to assign to the blog post.")