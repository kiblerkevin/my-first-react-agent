from pydantic import BaseModel, Field

class EvaluateBlogPostOutput(BaseModel):
    """Output schema for evaluate_blog_post tool"""
    criteria_scores: dict[str, int] = Field(description="Scores for each evaluation criterion.")
    criteria_reasoning: dict[str, str] = Field(description="Reasoning for the scores assigned to each criterion.")
    improvement_suggestions: list[str] = Field(description="List of suggestions for improving the blog post.")
