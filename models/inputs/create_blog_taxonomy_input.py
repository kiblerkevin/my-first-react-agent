from pydantic import BaseModel, Field


class CreateBlogTaxonomyInput(BaseModel):
    """Input schema for create_blog_taxonomy tool."""

    teams_covered: list[str] = Field(
        description='List of Chicago team names covered in the blog post.'
    )
    players_mentioned: list[str] = Field(
        default_factory=list,
        description='Flat list of all player names mentioned across article summaries.',
    )
