"""Pydantic models for the agent conversation context window."""

from pydantic import BaseModel


class UserMessage(BaseModel):
    """A user-role message in the conversation."""

    content: str
    role: str = 'user'


class AssistantMessage(BaseModel):
    """An assistant-role message in the conversation."""

    content: str
    role: str = 'assistant'


class ToolUse(BaseModel):
    """A tool invocation block within an assistant message."""

    type: str = 'tool_use'
    id: str
    name: str
    input: dict


class ToolUseMessage(BaseModel):
    """An assistant message containing tool use blocks."""

    role: str = 'assistant'
    content: list[ToolUse]


class ToolResult(BaseModel):
    """A tool result block within a user message."""

    type: str = 'tool_result'
    tool_use_id: str
    content: str
    is_error: bool


class ToolResultMessage(BaseModel):
    """A user message containing tool result blocks."""

    role: str = 'user'
    content: list[ToolResult]


class ContextWindow(BaseModel):
    """Ordered conversation history for an agent session."""

    conversation_history: list

    def add(
        self,
        message: UserMessage | AssistantMessage | ToolUseMessage | ToolResultMessage,
    ) -> None:
        """Append a message to the conversation history.

        Args:
            message: Any conversation message type.
        """
        self.conversation_history.append(message)
