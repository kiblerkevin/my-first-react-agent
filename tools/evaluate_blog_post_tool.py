import json
import yaml
from datetime import datetime, timezone

from tools.base_tool import BaseTool
from models.inputs.evaluate_blog_post_input import EvaluateBlogPostInput
from models.outputs.evaluate_blog_post_output import EvaluateBlogPostOutput
from agent.claude_client import ClaudeClient
from prompts.evaluate_blog_post_prompt import EVALUATE_BLOG_POST_PROMPT
from utils.logger.logger import setup_logger


logger = setup_logger(__name__)

CONFIG_PATH = 'config/llms.yaml'
CRITERIA = ['accuracy', 'completeness', 'readability', 'seo']


class EvaluateBlogPostTool(BaseTool):
    model_config = {"arbitrary_types_allowed": True, "extra": "allow"}

    input_model: type = EvaluateBlogPostInput

    name: str = "evaluate_blog_post"
    description: str = (
        "Evaluates a blog post draft on four criteria: accuracy, completeness, readability, and SEO. "
        "Returns per-criterion scores (1-10), reasoning, improvement suggestions, and an overall score. "
        "Call this tool after create_blog_draft. Can be called multiple times on the same post — "
        "use evaluation_id to distinguish between runs. Use overall_score across runs to decide "
        "whether to proceed to publishing."
    )
    input_schema: dict = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Blog post title."},
            "content": {"type": "string", "description": "Full HTML blog post body."},
            "excerpt": {"type": "string", "description": "First-pass SEO excerpt."},
            "summaries": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Article summaries used as accuracy ground truth."
            },
            "scores": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Game scores used as completeness ground truth."
            }
        },
        "required": ["title", "content", "excerpt"]
    }
    output_schema: dict = {
        "type": "object",
        "properties": {
            "evaluation_id": {"type": "string"},
            "overall_score": {"type": "number"},
            "criteria_scores": {"type": "object"},
            "criteria_reasoning": {"type": "object"},
            "improvement_suggestions": {"type": "object"}
        }
    }

    def __init__(self):
        super().__init__(
            name=self.model_fields['name'].default,
            description=self.model_fields['description'].default,
            input_schema=self.model_fields['input_schema'].default,
            output_schema=self.model_fields['output_schema'].default
        )
        with open(CONFIG_PATH, 'r') as f:
            config = yaml.safe_load(f)
        evaluator_config = config['claude_evaluator']
        self.claude_client = ClaudeClient(system_prompt=EVALUATE_BLOG_POST_PROMPT)
        self.claude_client.model = evaluator_config['model']
        self.claude_client.temperature = evaluator_config['temperature']
        self.claude_client.max_tokens = evaluator_config['max_tokens']

    def execute(self, input: EvaluateBlogPostInput) -> EvaluateBlogPostOutput:
        evaluation_id = datetime.now(timezone.utc).isoformat()
        user_message = self._build_prompt(input)

        try:
            response_text = self.claude_client.send_message(user_message)
            response_text = response_text.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip()
            parsed = json.loads(response_text)

            criteria_scores = {
                k: float(parsed.get('criteria_scores', {}).get(k, 0.0))
                for k in CRITERIA
            }
            overall_score = round(sum(criteria_scores.values()) / len(CRITERIA), 2)

            criteria_reasoning = {}
            for k, v in parsed.get('criteria_reasoning', {}).items():
                criteria_reasoning[k] = str(v) if not isinstance(v, str) else v

            improvement_suggestions = {}
            for k, v in parsed.get('improvement_suggestions', {}).items():
                if isinstance(v, list):
                    improvement_suggestions[k] = [str(s) for s in v]
                elif isinstance(v, str):
                    improvement_suggestions[k] = [v]
                else:
                    improvement_suggestions[k] = [str(v)]

            output = EvaluateBlogPostOutput(
                evaluation_id=evaluation_id,
                overall_score=overall_score,
                criteria_scores=criteria_scores,
                criteria_reasoning=criteria_reasoning,
                improvement_suggestions=improvement_suggestions
            )
            logger.info(
                f"Evaluation {evaluation_id}: overall={overall_score} | "
                + " | ".join(f"{k}={v}" for k, v in criteria_scores.items())
            )
            return output

        except Exception as e:
            logger.error(f"Error evaluating blog post: {e}")
            return EvaluateBlogPostOutput(evaluation_id=evaluation_id)

    def _build_prompt(self, input: EvaluateBlogPostInput) -> str:
        sections = [
            "BLOG POST:",
            f"Title: {input.title}",
            f"Excerpt: {input.excerpt}",
            f"Content:\n{input.content}",
            "\nSUMMARIES (ground truth for accuracy):",
            json.dumps(input.summaries, indent=2),
            "\nSCORES (ground truth for completeness):",
            json.dumps(input.scores, indent=2)
        ]

        if input.rejection_feedback:
            sections.append(
                f"\nPREVIOUS REJECTION FEEDBACK (check whether this was addressed):\n{input.rejection_feedback}"
            )

        return '\n'.join(sections)
