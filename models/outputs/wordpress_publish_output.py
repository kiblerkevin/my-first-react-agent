from pydantic import BaseModel, Field
from typing import Optional


class WordPressPublishOutput(BaseModel):
    """Output schema for wordpress_publish tool"""
    post_id: int = Field(default=0, description="WordPress post ID.")
    post_url: str = Field(default="", description="URL of the published draft post.")
    status: str = Field(default="", description="Post status (draft).")
    categories_resolved: dict[str, int] = Field(
        default_factory=dict,
        description="Mapping of category name to WordPress ID."
    )
    tags_resolved: dict[str, int] = Field(
        default_factory=dict,
        description="Mapping of tag name to WordPress ID."
    )
    error: Optional[str] = Field(default=None, description="Error message if publishing failed.")
