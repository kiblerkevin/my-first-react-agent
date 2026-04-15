from pydantic import BaseModel, Field


class CreateBlogTaxonomyOutput(BaseModel):
    """Output schema for create_blog_taxonomy tool"""
    categories: list[dict] = Field(
        default_factory=list,
        description="Assigned categories, each with name, id (local), and wordpress_id (nullable)."
    )
    tags: list[dict] = Field(
        default_factory=list,
        description="Assigned tags, each with name, id (local), and wordpress_id (nullable)."
    )
    new_categories: list[str] = Field(
        default_factory=list,
        description="Names of categories created during this run."
    )
    new_tags: list[str] = Field(
        default_factory=list,
        description="Names of tags created during this run."
    )
