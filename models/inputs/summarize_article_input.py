from pydantic import BaseModel, Field


class SummarizeArticleInput(BaseModel):
    """Input schema for summarize_article tool"""
    url: str = Field(description="URL of the article to summarize.")
    title: str = Field(description="Title of the article.")
    team: str = Field(description="Chicago team this article relates to.")
    published_at: str = Field(default="", description="ISO 8601 publish date of the article.")
