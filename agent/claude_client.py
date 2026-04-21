"""Anthropic Claude API client with retry, Gemini fallback, and Langfuse observability."""

import time
from typing import Any

import yaml
from anthropic import (
    Anthropic,
    APIConnectionError,
    AuthenticationError,
    InternalServerError,
    RateLimitError,
)
from anthropic.types import Message
from dotenv import load_dotenv
from langfuse import observe

from utils.logger.logger import setup_logger
from utils.secrets import get_secret

load_dotenv()

LLMS_CONFIG_PATH = 'config/llms.yaml'
ORCHESTRATION_CONFIG_PATH = 'config/orchestration.yaml'

logger = setup_logger(__name__)

# Exceptions that trigger fallback (Claude is down, not our fault)
_FALLBACK_ERRORS = (APIConnectionError, AuthenticationError, InternalServerError)


class ClaudeClient:
    """Wrapper around the Anthropic Messages API with retry, fallback, and observability."""

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
        self._fallback_config: dict[str, Any] = config['claude'].get('fallback', {})

        with open(ORCHESTRATION_CONFIG_PATH, 'r') as f:
            rl_config: dict[str, Any] = yaml.safe_load(f).get('rate_limiting', {})
        self._rl_max_retries: int = rl_config.get('max_retries', 3)
        self._rl_base_delay: float = rl_config.get('base_delay_seconds', 1.0)

    def _get_fallback_client(self) -> Any:
        """Create a Gemini fallback client from config.

        Returns:
            GeminiClient instance, or None if fallback not configured.
        """
        if (
            not self._fallback_config
            or self._fallback_config.get('provider') != 'gemini'
        ):
            return None
        from agent.gemini_client import GeminiClient

        return GeminiClient(
            system_prompt=self.system_prompt,
            model=self._fallback_config.get('model', 'gemini-2.5-flash'),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

    @observe(as_type='generation')
    def send_messages_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        tool_choice: dict[str, str] | None = None,
    ) -> Message:
        """Send messages with tool definitions to Claude, falling back to Gemini.

        Args:
            messages: Conversation messages.
            tools: Tool definitions for Claude.
            tool_choice: Optional forced tool selection.

        Returns:
            Claude Message response (or adapted Gemini response).

        Raises:
            Exception: If both Claude and fallback fail.
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
                    return self._fallback_with_tools(
                        messages,
                        tools,
                        tool_choice,
                        f'Rate limit exceeded after {self._rl_max_retries} retries: {e!s}',
                    )
            except _FALLBACK_ERRORS as e:
                return self._fallback_with_tools(
                    messages,
                    tools,
                    tool_choice,
                    f'Claude API error: {e!s}',
                )
            except Exception as e:
                raise Exception(f'Failed to create message: {e!s}') from e
        raise Exception('Unreachable')  # satisfies mypy

    def _fallback_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        tool_choice: dict[str, str] | None,
        reason: str,
    ) -> Message:
        """Attempt Gemini fallback for tool-use messages.

        Args:
            messages: Conversation messages.
            tools: Tool definitions.
            tool_choice: Optional forced tool selection.
            reason: Why fallback was triggered.

        Returns:
            Adapted Gemini response.

        Raises:
            Exception: If fallback is not configured or also fails.
        """
        fallback = self._get_fallback_client()
        if not fallback:
            raise Exception(f'{reason} (no fallback configured)')
        logger.warning(f'Falling back to Gemini: {reason}')
        return fallback.send_messages_with_tools(messages, tools, tool_choice)

    @observe(as_type='generation')
    def send_message(self, user_message: str) -> str:
        """Send a single user message to Claude, falling back to Gemini.

        Args:
            user_message: The user's message text.

        Returns:
            Text response from Claude or Gemini.

        Raises:
            Exception: If both Claude and fallback fail.
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
                    return self._fallback_send_message(
                        user_message,
                        f'Rate limit exceeded after {self._rl_max_retries} retries: {e!s}',
                    )
            except _FALLBACK_ERRORS as e:
                return self._fallback_send_message(
                    user_message,
                    f'Claude API error: {e!s}',
                )
            except Exception as e:
                raise Exception(f'Failed to create message: {e!s}') from e
        raise Exception('Unreachable')  # satisfies mypy

    def _fallback_send_message(self, user_message: str, reason: str) -> str:
        """Attempt Gemini fallback for a simple message.

        Args:
            user_message: The user's message text.
            reason: Why fallback was triggered.

        Returns:
            Text response from Gemini.

        Raises:
            Exception: If fallback is not configured or also fails.
        """
        fallback = self._get_fallback_client()
        if not fallback:
            raise Exception(f'{reason} (no fallback configured)')
        logger.warning(f'Falling back to Gemini: {reason}')
        return fallback.send_message(user_message)
