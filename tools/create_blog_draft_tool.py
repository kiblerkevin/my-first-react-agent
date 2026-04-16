import json
import yaml
from collections import defaultdict
from datetime import datetime, timezone

from tools.base_tool import BaseTool
from models.inputs.create_blog_draft_input import CreateBlogDraftInput
from models.outputs.create_blog_draft_output import CreateBlogDraftOutput
from agent.claude_client import ClaudeClient
from prompts.create_blog_draft_prompt import CREATE_BLOG_DRAFT_PROMPT, CREATE_BLOG_DRAFT_REVISION_PROMPT
from utils.logger.logger import setup_logger


logger = setup_logger(__name__)

CONFIG_PATH = 'config/llms.yaml'


class CreateBlogDraftTool(BaseTool):
    model_config = {"arbitrary_types_allowed": True, "extra": "allow"}

    input_model: type = CreateBlogDraftInput

    name: str = "create_blog_draft"
    description: str = (
        "Creates a full HTML blog post draft from article summaries and game scores. "
        "Sections include: previous day's scores with notes, article summaries grouped by team, "
        "and today's scheduled games. Call this tool after summarize_article has been called "
        "for all relevant articles and fetch_scores has been called for game data."
    )
    input_schema: dict = {
        "type": "object",
        "properties": {
            "summaries": {
                "type": "array",
                "description": "Article summaries from summarize_article with is_relevant=true.",
                "items": {"type": "object"}
            },
            "scores": {
                "type": "array",
                "description": "Game scores from fetch_scores.",
                "items": {"type": "object"}
            }
        },
        "required": ["summaries", "scores"]
    }
    output_schema: dict = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "content": {"type": "string"},
            "excerpt": {"type": "string"},
            "teams_covered": {"type": "array", "items": {"type": "string"}},
            "article_count": {"type": "integer"}
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
        drafter_config = config['claude_drafter']
        self.claude_client = ClaudeClient(system_prompt=CREATE_BLOG_DRAFT_PROMPT)
        self.claude_client.model = drafter_config['model']
        self.claude_client.temperature = drafter_config['temperature']
        self.claude_client.max_tokens = drafter_config['max_tokens']
        self.claude_client.cost_per_million_input = drafter_config.get('cost_per_million_input', 0.0)
        self.claude_client.cost_per_million_output = drafter_config.get('cost_per_million_output', 0.0)

    def execute(self, input: CreateBlogDraftInput) -> CreateBlogDraftOutput:
        today = datetime.now(timezone.utc).date()

        previous_scores = []
        todays_games = []
        for score in input.scores:
            try:
                game_date = datetime.fromisoformat(
                    score['date'].replace('Z', '+00:00')
                ).date()
            except Exception:
                game_date = None

            if score.get('completed'):
                previous_scores.append(score)
            elif game_date and game_date >= today:
                todays_games.append(score)

        relevant_summaries = [s for s in input.summaries if s.get('is_relevant', True)]
        summaries_by_team = defaultdict(list)
        for s in relevant_summaries:
            summaries_by_team[s.get('team', 'Unknown')].append(s)

        is_revision = input.current_draft and input.revision_notes
        if is_revision:
            self.claude_client.system_prompt = CREATE_BLOG_DRAFT_REVISION_PROMPT
            user_message = self._build_revision_prompt(
                input.current_draft, input.revision_notes, previous_scores, todays_games, summaries_by_team, input.rejection_feedback
            )
        else:
            self.claude_client.system_prompt = CREATE_BLOG_DRAFT_PROMPT
            user_message = self._build_prompt(previous_scores, todays_games, summaries_by_team, input.rejection_feedback)

        try:
            response_text = self.claude_client.send_message(user_message)
            response_text = response_text.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip()
            parsed = json.loads(response_text)

            output = CreateBlogDraftOutput(
                title=parsed.get('title', ''),
                content=parsed.get('content', ''),
                excerpt=parsed.get('excerpt', ''),
                teams_covered=parsed.get('teams_covered', []),
                article_count=len(relevant_summaries)
            )
            logger.info(f"Blog draft created: '{output.title}' covering {output.teams_covered}")
            return output

        except Exception as e:
            logger.error(f"Error creating blog draft: {e}")
            return CreateBlogDraftOutput()

    def _build_prompt(self, previous_scores, todays_games, summaries_by_team, rejection_feedback=None) -> str:
        sections = []

        if rejection_feedback:
            sections.append(f"PREVIOUS REJECTION FEEDBACK (address this in the draft):\n{rejection_feedback}\n")

        sections.append("COMPLETED GAMES (previous day):")
        if previous_scores:
            sections.append(json.dumps(previous_scores, indent=2))
        else:
            sections.append("None.")

        sections.append("\nSCHEDULED GAMES (today):")
        if todays_games:
            sections.append(json.dumps(todays_games, indent=2))
        else:
            sections.append("None.")

        sections.append("\nARTICLE SUMMARIES BY TEAM:")
        if summaries_by_team:
            sections.append(json.dumps(dict(summaries_by_team), indent=2))
        else:
            sections.append("None.")

        return '\n'.join(sections)

    def _build_revision_prompt(self, current_draft, revision_notes, previous_scores, todays_games, summaries_by_team, rejection_feedback=None) -> str:
        sections = []

        if rejection_feedback:
            sections.append(f"PREVIOUS REJECTION FEEDBACK (address this in the revision):\n{rejection_feedback}\n")

        sections.extend([
            "CURRENT DRAFT:",
            current_draft,
            "\nREVISION NOTES (address each of these):",
            json.dumps(revision_notes, indent=2),
            "\nSCORES (for reference):",
            json.dumps(previous_scores + todays_games, indent=2),
            "\nARTICLE SUMMARIES (for reference):",
            json.dumps(dict(summaries_by_team), indent=2)
        ])
        return '\n'.join(sections)
