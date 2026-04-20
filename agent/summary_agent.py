"""Legacy summary agent stub. Superseded by tool-based summarization."""

from typing import Any

from agent.claude_client import ClaudeClient
from agent.context_window import (
    AssistantMessage,
    ContextWindow,
    ToolResult,
    ToolResultMessage,
    ToolUse,
    ToolUseMessage,
    UserMessage,
)


class SummaryAgent:
    """Basic agent for article summarization (unused — kept for reference)."""

    def __init__(
        self,
        context: ContextWindow,
        claude_client: ClaudeClient,
    ) -> None:
        """Initialize with context and Claude client.

        Args:
            context: Conversation context window.
            claude_client: Claude API client.
        """
        self.claude_client = claude_client
        self.context = context
        self.tools: list[Any] = []

    def send_message(self, user_message: str) -> str:
        """Send a user message and return the agent's response.

        Args:
            user_message: The user's message text.

        Returns:
            Agent's text response.
        """
        self.context.add(UserMessage(content=user_message))
        response = self.act()
        self.context.add(AssistantMessage(content=response))
        return response

    def act(self) -> str:
        """Execute one iteration of the tool-use loop.

        Returns:
            Agent's text response.
        """
        response = self.claude_client.send_messages_with_tools(
            messages=[msg.model_dump() for msg in self.context.conversation_history],
            tools=[tool.model_dump() for tool in self.tools],
        )

        tool_use_id = 1

        if response.stop_reason == 'tool_use':
            for content_block in response.content:
                if content_block.type == 'tool_use':
                    tool_use = ToolUse(
                        id=str(tool_use_id),
                        name=content_block.name,
                        input=content_block.input,
                    )
                    tool_use_msg = ToolUseMessage(content=[tool_use])
                    self.context.add(tool_use_msg)

                    tool_result_response = self._execute_tool(
                        tool_use.name, tool_use.input
                    )

                    tool_result = ToolResult(
                        tool_use_id=str(tool_use_id),
                        content=tool_result_response,
                        is_error=False,
                    )
                    tool_result_message = ToolResultMessage(content=[tool_result])
                    self.context.add(tool_result_message)

                    tool_use_id += 1

            return self.act()

        return response.content[0].text if response.content else ''

    def _execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Execute a tool by name. Not implemented in this stub.

        Args:
            tool_name: Name of the tool.
            tool_input: Input dict for the tool.

        Returns:
            Error message (no tools registered).
        """
        try:
            pass
        except Exception as e:
            return f'Error executing tool {tool_name}: {e!s}'
        return ''

    def summarize_articles(
        self, source_articles: list[dict[str, str]]
    ) -> dict[str, str] | None:
        """Summarize source articles. Not implemented.

        Args:
            source_articles: List of article dicts.

        Returns:
            None (not implemented).
        """
        return None
