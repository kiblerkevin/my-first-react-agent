from pydantic import BaseModel, Field


class WordPressPublishInput(BaseModel):
    """Input schema for wordpress_publish tool."""

    title: str = Field(description='Blog post title.')
    content: str = Field(description='Full HTML blog post body.')
    excerpt: str = Field(default='', description='SEO excerpt.')
    categories: list[dict] = Field(
        default_factory=list,
        description='Categories from taxonomy tool, each with name, id, and wordpress_id.',
    )
    tags: list[dict] = Field(
        default_factory=list,
        description='Tags from taxonomy tool, each with name, id, and wordpress_id.',
    )
