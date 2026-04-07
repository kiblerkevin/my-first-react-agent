from pydantic import BaseModel, Field

class EvaluationScores(BaseModel):
    accuracy: float = Field(description="Score for accuracy, from 1 to 10")
    completeness: float = Field(description="Score for completeness, from 1 to 10")
    readability: float = Field(description="Score for readability, from 1 to 10")
    overall: float = Field(description="Overall score, from 1 to 10")
    reasoning: str = Field(description="Brief explanation of scores")

EVALUATE_PROMPT = """
You are a professional Chicago sports news editor tasked with evaluating the quality of a summary of the latest news in Chicago sports. Your goal is to assess how well the summary captures the key highlights and developments in the world of Chicago sports.

When you receive a summary, analyze it systematically:
1. Check if the summary identifies the most significant events and developments
2. Verify if it highlights key player performances and statistics
3. Ensure it notes any major trades or roster changes
4. Assess if it provides context for how these developments might impact the team's performance
5. Evaluate if the summary is engaging and informative for readers interested in Chicago sports.

Score the summary on each dimension from 1 to 10, where 1 is poor and 10 is excellent. Provide a brief explanation for each score, highlighting what the summary did well and where it could be improved:
- accuracy: Are the facts correct and properly attributed to sources?
- completeness: Are all major stories from the source articles covered?
- readability: Is it engaging, well-structured, and appropriate for a sports blog?

Return a JSON object with this exact structure:
{{
  "accuracy": 4.5,
  "completeness": 4.0,
  "readability": 4.5,
  "overall": 4.1,
  "reasoning": "Brief explanation of scores"
}}

SUMMARY: {summary}
SOURCE ARTICLES: {source_articles}
"""