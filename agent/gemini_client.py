"""Google Gemini API client as fallback for Claude."""

from typing import Any

from google import genai
from langfuse import observe

from agent.gemini_adapter import (
    AdaptedMessage,
    adapt_messages,
    adapt_response,
    adapt_tools,
)
from utils.logger.logger import setup_logger
from utils.secrets import get_secret

logger = setup_logger(__name__)


class GeminiClient:
    """Wrapper around the Google Gemini API, matching ClaudeClient's interface."""

    def __init__(
        self,
        system_prompt: str,
        model: str = 'gemini-2.5-flash',
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> None:
        """Initialize the Gemini client.

        Args:
            system_prompt: System instruction for all messages.
            model: Gemini model name.
            temperature: Sampling temperature.
            max_tokens: Maximum output tokens.
        """
        self.system_prompt = system_prompt
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        api_key = get_secret('GOOGLE_API_KEY')
        self.client = genai.Client(api_key=api_key)

    @observe(as_type='generation')
    def send_messages_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        tool_choice: dict[str, str] | None = None,
    ) -> AdaptedMessage:
        """Send messages with tool definitions to Gemini.

        Args:
            messages: Conversation messages in Claude format.
            tools: Tool definitions in Claude format.
            tool_choice: Optional forced tool selection (best-effort mapping).

        Returns:
            AdaptedMessage matching Claude's response format.
        """
        system_instruction, contents = adapt_messages(messages, self.system_prompt)
        gemini_tools = adapt_tools(tools) if tools else None

        config: dict[str, Any] = {
            'temperature': self.temperature,
            'max_output_tokens': self.max_tokens,
        }
        if system_instruction:
            config['system_instruction'] = system_instruction

        # Map tool_choice to Gemini's tool_config
        if tool_choice and tool_choice.get('type') == 'tool':
            config['tool_config'] = {
                'function_calling_config': {'mode': 'ANY'},
            }

        kwargs: dict[str, Any] = {
            'model': self.model,
            'contents': contents,
            'config': config,
        }
        if gemini_tools:
            kwargs['tools'] = gemini_tools

        response = self.client.models.generate_content(**kwargs)
        logger.info(f'Gemini fallback response from {self.model}')
        return adapt_response(response)

    @observe(as_type='generation')
    def send_message(self, user_message: str) -> str:
        """Send a single user message to Gemini and return the text response.

        Args:
            user_message: The user's message text.

        Returns:
            Gemini's text response.
        """
        config: dict[str, Any] = {
            'temperature': self.temperature,
            'max_output_tokens': self.max_tokens,
        }
        if self.system_prompt:
            config['system_instruction'] = self.system_prompt

        response = self.client.models.generate_content(
            model=self.model,
            contents=user_message,
            config=config,
        )
        text = response.text or ''
        logger.info(f'Gemini fallback text response from {self.model}')
        return text
