from pydantic import BaseModel, Field

class SummarizeArticlesOutput(BaseModel):
    """Output schema for summarize_articles tool"""
    title: str = Field(description="The title of the generated blog post. (e.g., 'Chicago Sports Digest: Bears Draft Rumors and Bulls Trade Talk')")
    content: str = Field(description="The full digest formatted in HTML. Use <h2> tags for team names, <p> for summaries, and <ul>/<li> for bulleted highlights.")
    excerpt: str = Field(description="A brief 1-2 sentence HTML summary of the overall digest.")
    generated_taxonomies: dict[str, list[str]] = Field(description="Generated categories and tags based on the content, such as {'categories_text': ['Daily Digest', 'Chicago Bears'], 'tags_text': ['NFL Draft', 'Zach LaVine']}.")
    mcp_payload: dict[str, list[int]] = Field(description="Payload for WordPress REST API, including resolved category and tag IDs, such as {'categories': [12, 34], 'tags': [56, 78]}.")
    metadata: dict[str, str] = Field(description="SEO optimized metadata about the blog post, such as keywords, summary, etc. Compatible with Yoast, Rank Math, and All in One SEO plugins. e.g. {'_yoast_wpseo_metadesc': 'A concise summary for SEO purposes', 'featured_image_prompt': 'A prompt for generating a featured image related to Chicago sports.'}")