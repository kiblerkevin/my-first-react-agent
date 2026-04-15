from pydantic import BaseModel, Field


class EvaluateBlogPostOutput(BaseModel):
    """Output schema for evaluate_blog_post tool"""
    evaluation_id: str = Field(default="", description="ISO timestamp identifying this evaluation run.")
    overall_score: float = Field(default=0.0, description="Mean of the four criteria scores (1-10).")
    criteria_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Scores 1-10 for each criterion: accuracy, completeness, readability, seo."
    )
    criteria_reasoning: dict[str, str] = Field(
        default_factory=dict,
        description="Per-criterion explanation of the score assigned."
    )
    improvement_suggestions: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Improvement suggestions structured per criterion."
    )
