import json
import yaml
from bs4 import BeautifulSoup

from tools.base_tool import BaseTool
from models.inputs.summarize_article_input import SummarizeArticleInput
from models.outputs.summarize_article_output import SummarizeArticleOutput
from agent.claude_client import ClaudeClient
from prompts.summarize_article_prompt import SUMMARIZE_ARTICLE_PROMPT
from memory.memory import Memory
from utils.http import rate_limited_request
from utils.logger.logger import setup_logger


logger = setup_logger(__name__)

CONFIG_PATH = 'config/llms.yaml'
MAX_CONTENT_CHARS = 3000


class SummarizeArticleTool(BaseTool):
    model_config = {"arbitrary_types_allowed": True, "extra": "allow"}

    input_model: type = SummarizeArticleInput

    name: str = "summarize_article"
    description: str = (
        "Fetches and summarizes a single news article by URL. "
        "Returns a 2-3 sentence summary, event type, players mentioned, and a relevance flag. "
        "Call this tool for each article returned by fetch_articles that you want to include in the blog post. "
        "Do not call this for every article — only those whose title suggests they are relevant."
    )
    input_schema: dict = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL of the article to summarize."},
            "title": {"type": "string", "description": "Title of the article."},
            "team": {"type": "string", "description": "Chicago team this article relates to."},
            "published_at": {"type": "string", "description": "ISO 8601 publish date of the article."}
        },
        "required": ["url", "title", "team"]
    }
    output_schema: dict = {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "team": {"type": "string"},
            "summary": {"type": "string"},
            "event_type": {"type": "string"},
            "players_mentioned": {"type": "array", "items": {"type": "string"}},
            "is_relevant": {"type": "boolean"}
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
        summarizer_config = config['claude_summarizer']
        self.claude_client = ClaudeClient(
            system_prompt=SUMMARIZE_ARTICLE_PROMPT,
        )
        self.claude_client.model = summarizer_config['model']
        self.claude_client.temperature = summarizer_config['temperature']
        self.claude_client.max_tokens = summarizer_config['max_tokens']
        self.claude_client.cost_per_million_input = summarizer_config.get('cost_per_million_input', 0.0)
        self.claude_client.cost_per_million_output = summarizer_config.get('cost_per_million_output', 0.0)
        self.memory = Memory()

    def execute(self, input: SummarizeArticleInput) -> SummarizeArticleOutput:
        # Check memory for existing summary
        cached = self.memory.get_article_summary(input.url)
        if cached:
            logger.info(f"Using cached summary for {input.team}: {input.title[:60]}")
            return SummarizeArticleOutput(**cached)

        content = self._fetch_content(input.url)
        title_only = content is None

        user_message = self._build_prompt(input, content)

        try:
            response_text = self.claude_client.send_message(user_message)
            response_text = response_text.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip()
            parsed = json.loads(response_text)

            output = SummarizeArticleOutput(
                url=input.url,
                team=input.team,
                summary=parsed.get('summary', ''),
                event_type=parsed.get('event_type', 'other'),
                players_mentioned=parsed.get('players_mentioned', []),
                is_relevant=False if title_only else parsed.get('is_relevant', True)
            )
            logger.info(f"Summarized article for {input.team}: {input.title[:60]}")
            self.memory.save_article_summary(output.model_dump())
            return output

        except Exception as e:
            logger.error(f"Error summarizing article {input.url}: {e}")
            return SummarizeArticleOutput(
                url=input.url,
                team=input.team,
                summary=input.title,
                event_type='other',
                is_relevant=False
            )

    def _fetch_content(self, url: str) -> str | None:
        try:
            response = rate_limited_request('GET', url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                tag.decompose()

            text = soup.get_text(separator=' ', strip=True)
            return text[:MAX_CONTENT_CHARS]

        except Exception as e:
            logger.warning(f"Could not fetch article content from {url}: {e}")
            return None

    def _build_prompt(self, input: SummarizeArticleInput, content: str | None) -> str:
        lines = [
            f"Team: {input.team}",
            f"Title: {input.title}",
            f"Published: {input.published_at or 'unknown'}",
        ]
        if content:
            lines.append(f"Content: {content}")
        else:
            lines.append("Content: unavailable — summarize from title only and set is_relevant to false.")
        return '\n'.join(lines)
