"""Anthropic Claude API client with rate limit retry and Langfuse observability."""

import time
from typing import Any

import yaml
from anthropic import Anthropic, RateLimitError
from anthropic.types import Message
from dotenv import load_dotenv
from langfuse import observe

from utils.logger.logger import setup_logger
from utils.secrets import get_secret

load_dotenv()

LLMS_CONFIG_PATH = 'config/llms.yaml'
ORCHESTRATION_CONFIG_PATH = 'config/orchestration.yaml'

logger = setup_logger(__name__)


class ClaudeClient:
    """Wrapper around the Anthropic Messages API with retry and observability."""

    def __init__(self, system_prompt: str, output_schema: object = None) -> None:
        """Initialize client with system prompt and config from YAML files.

        Args:
            system_prompt: System prompt for all messages.
            output_schema: Optional output schema (reserved for future use).
        """
        self.system_prompt = system_prompt
        self.client = Anthropic(api_key=get_secret('ANTHROPIC_API_KEY'))
        self.output_schema = output_schema

        with open(LLMS_CONFIG_PATH, 'r') as f:
            config = yaml.safe_load(f)
        self.model: str = config['claude']['model']
        self.temperature: float = config['claude']['temperature']
        self.max_tokens: int = config['claude']['max_tokens']

        with open(ORCHESTRATION_CONFIG_PATH, 'r') as f:
            rl_config: dict[str, Any] = yaml.safe_load(f).get('rate_limiting', {})
        self._rl_max_retries: int = rl_config.get('max_retries', 3)
        self._rl_base_delay: float = rl_config.get('base_delay_seconds', 1.0)

    @observe(as_type='generation')
    def send_messages_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        tool_choice: dict[str, str] | None = None,
    ) -> Message:
        """Send messages with tool definitions to Claude.

        Args:
            messages: Conversation messages.
            tools: Tool definitions for Claude.
            tool_choice: Optional forced tool selection.

        Returns:
            Claude Message response.

        Raises:
            Exception: If rate limit persists or API call fails.
        """
        for attempt in range(self._rl_max_retries + 1):
            try:
                kwargs: dict[str, Any] = dict(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    system=self.system_prompt,
                    messages=messages,
                    tools=tools,
                )
                if tool_choice:
                    kwargs['tool_choice'] = tool_choice
                response = self.client.messages.create(**kwargs)
                return response
            except RateLimitError as e:
                if attempt < self._rl_max_retries:
                    delay = self._rl_base_delay * (2**attempt)
                    logger.warning(
                        f'Anthropic rate limited — retrying in {delay:.1f}s '
                        f'(attempt {attempt + 1}/{self._rl_max_retries})'
                    )
                    time.sleep(delay)
                else:
                    raise Exception(
                        f'Anthropic rate limit exceeded after '
                        f'{self._rl_max_retries} retries: {e!s}'
                    ) from e
            except Exception as e:
                raise Exception(f'Failed to create message: {e!s}') from e
        raise Exception('Unreachable')  # satisfies mypy

    @observe(as_type='generation')
    def send_message(self, user_message: str) -> str:
        """Send a single user message to Claude and return the text response.

        Args:
            user_message: The user's message text.

        Returns:
            Claude's text response.

        Raises:
            Exception: If rate limit persists or API call fails.
        """
        for attempt in range(self._rl_max_retries + 1):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    system=self.system_prompt,
                    messages=[{'role': 'user', 'content': user_message}],
                )
                return response.content[0].text
            except RateLimitError as e:
                if attempt < self._rl_max_retries:
                    delay = self._rl_base_delay * (2**attempt)
                    logger.warning(
                        f'Anthropic rate limited — retrying in {delay:.1f}s '
                        f'(attempt {attempt + 1}/{self._rl_max_retries})'
                    )
                    time.sleep(delay)
                else:
                    raise Exception(
                        f'Anthropic rate limit exceeded after '
                        f'{self._rl_max_retries} retries: {e!s}'
                    ) from e
            except Exception as e:
                raise Exception(f'Failed to create message: {e!s}') from e
        raise Exception('Unreachable')  # satisfies mypy
