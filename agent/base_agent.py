"""Base agent with tool-use loop, revision tracking, and budget guards."""

import json
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
from utils.logger.logger import setup_logger

logger = setup_logger(__name__)


class BaseAgent:
    """Agent that iterates tool calls until the LLM returns a text response."""

    def __init__(
        self,
        context: ContextWindow,
        claude_client: ClaudeClient,
        max_tool_calls: int | None = None,
        force_first_tool: str | None = None,
        required_tool_context: dict[str, dict[str, Any]] | None = None,
        revision_tracking: dict[str, str] | None = None,
    ) -> None:
        """Initialize the agent.

        Args:
            context: Conversation context window.
            claude_client: Claude API client.
            max_tool_calls: Maximum tool invocations before stopping.
            force_first_tool: Tool name to force on the first call.
            required_tool_context: Fields to inject if the LLM omits them.
            revision_tracking: Config mapping draft_tool and evaluate_tool names.
        """
        self.claude_client = claude_client
        self.context = context
        self.tools: dict[str, Any] = {}
        self.max_tool_calls = max_tool_calls
        self.tool_call_count: int = 0
        self.force_first_tool = force_first_tool

        self.required_tool_context: dict[str, dict[str, Any]] = (
            required_tool_context or {}
        )

        self._revision_config = revision_tracking
        self._last_draft_output: dict[str, Any] | None = None
        self._last_eval_suggestions: dict[str, list[str]] | None = None
        self._last_tool_name: str | None = None
        self._limit_extended: bool = False

    def send_message(self, user_message: str) -> str:
        """Send a user message and return the agent's final text response.

        Args:
            user_message: The user's message text.

        Returns:
            Agent's text response after all tool calls complete.
        """
        self.context.add(UserMessage(content=user_message))
        response = self.act()
        self.context.add(AssistantMessage(content=response))
        return response

    def act(self) -> str:
        """Execute one iteration of the tool-use loop.

        Returns:
            Agent's text response, or a limit-reached message.
        """
        if self._is_over_budget():
            return 'Tool call limit reached. Returning best available result.'

        response = self.claude_client.send_messages_with_tools(
            messages=[msg.model_dump() for msg in self.context.conversation_history],
            tools=[
                {
                    'name': tool.name,
                    'description': tool.description,
                    'input_schema': tool.input_schema,
                }
                for tool in self.tools.values()
            ],
            tool_choice=self._get_tool_choice(),
        )

        has_tool_use = any(
            getattr(block, 'type', None) == 'tool_use'
            for block in (response.content or [])
        )

        if has_tool_use:
            self._process_tool_blocks(response.content)
            return self.act()

        return self._extract_text(response.content)

    # --- Private helpers ---

    def _is_over_budget(self) -> bool:
        """Check if the tool call budget is exhausted, with one-time extension."""
        if not self.max_tool_calls or self.tool_call_count < self.max_tool_calls:
            return False

        if (
            self._revision_config
            and self._last_tool_name == self._revision_config.get('draft_tool')
            and not self._limit_extended
        ):
            self._limit_extended = True
            self.max_tool_calls += 1
            logger.warning(
                f'Extended tool call limit to {self.max_tool_calls} '
                f'to allow final evaluation after draft.'
            )
            return False

        logger.warning(
            f'Tool call limit reached ({self.max_tool_calls}). Stopping agent.'
        )
        return True

    def _get_tool_choice(self) -> dict[str, str] | None:
        """Return forced tool choice for the first call, or None."""
        if self.force_first_tool and self.tool_call_count == 0:
            return {'type': 'tool', 'name': self.force_first_tool}
        return None

    def _process_tool_blocks(self, content_blocks: list[Any]) -> None:
        """Execute each tool_use block in the response and record results."""
        tool_use_id = 1
        for block in content_blocks:
            if block.type != 'tool_use':
                continue

            if (
                self.max_tool_calls
                and self.tool_call_count >= self.max_tool_calls
            ):
                logger.warning(
                    f'Tool call limit reached mid-response '
                    f'({self.max_tool_calls}). Stopping.'
                )
                self.context.add(
                    ToolResultMessage(
                        content=[
                            ToolResult(
                                tool_use_id=str(tool_use_id),
                                content='Tool call limit reached. Please return your best result now.',
                                is_error=True,
                            )
                        ]
                    )
                )
                return

            tool_input = dict(block.input)
            tool_input = self._inject_required_context(block.name, tool_input)
            tool_input = self._inject_revision_context(block.name, tool_input)

            self.context.add(
                ToolUseMessage(
                    content=[
                        ToolUse(
                            id=str(tool_use_id),
                            name=block.name,
                            input=tool_input,
                        )
                    ]
                )
            )

            result_json = self._execute_tool(block.name, tool_input)
            self.tool_call_count += 1
            self._last_tool_name = block.name
            logger.info(
                f'Tool call {self.tool_call_count}/'
                f'{self.max_tool_calls or "∞"}: {block.name}'
            )

            self._track_revision_output(block.name, result_json)

            self.context.add(
                ToolResultMessage(
                    content=[
                        ToolResult(
                            tool_use_id=str(tool_use_id),
                            content=result_json,
                            is_error=False,
                        )
                    ]
                )
            )
            tool_use_id += 1

    @staticmethod
    def _extract_text(content_blocks: list[Any]) -> str:
        """Extract text from response content blocks."""
        for block in content_blocks or []:
            if hasattr(block, 'text'):
                return block.text
        return ''

    def _inject_required_context(
        self, tool_name: str, tool_input: dict[str, Any]
    ) -> dict[str, Any]:
        """Merge required context into tool input, warn on missing fields.

        Args:
            tool_name: Name of the tool being called.
            tool_input: Input dict from the LLM.

        Returns:
            Updated tool input with injected fields.
        """
        required = self.required_tool_context.get(tool_name, {})
        for field, value in required.items():
            if not tool_input.get(field):
                logger.warning(
                    f"LLM omitted required field '{field}' for {tool_name} "
                    f'— injecting from context.'
                )
                tool_input[field] = value
        return tool_input

    def _inject_revision_context(
        self, tool_name: str, tool_input: dict[str, Any]
    ) -> dict[str, Any]:
        """Auto-inject current_draft and revision_notes on subsequent draft calls.

        Args:
            tool_name: Name of the tool being called.
            tool_input: Input dict from the LLM.

        Returns:
            Updated tool input with revision context.
        """
        if not self._revision_config:
            return tool_input

        draft_tool = self._revision_config.get('draft_tool')
        if tool_name != draft_tool or not self._last_draft_output:
            return tool_input

        if not tool_input.get('current_draft') and self._last_draft_output.get(
            'content'
        ):
            logger.warning(
                "LLM omitted 'current_draft' on revision call "
                '— injecting previous draft.'
            )
            tool_input['current_draft'] = self._last_draft_output['content']

        if not tool_input.get('revision_notes') and self._last_eval_suggestions:
            logger.warning(
                "LLM omitted 'revision_notes' on revision call "
                '— injecting evaluation suggestions.'
            )
            tool_input['revision_notes'] = self._last_eval_suggestions

        return tool_input

    def _track_revision_output(self, tool_name: str, result_json: str) -> None:
        """Store draft/eval outputs for revision injection on subsequent calls.

        Args:
            tool_name: Name of the tool that produced the result.
            result_json: JSON string of the tool result.
        """
        if not self._revision_config:
            return

        try:
            result = json.loads(result_json)
        except (json.JSONDecodeError, TypeError):
            return

        if tool_name == self._revision_config.get('draft_tool'):
            if 'title' in result and 'content' in result:
                self._last_draft_output = result

        elif (
            tool_name == self._revision_config.get('evaluate_tool')
            and 'improvement_suggestions' in result
        ):
            self._last_eval_suggestions = result['improvement_suggestions']

    def _execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Execute a registered tool and return the JSON result.

        Args:
            tool_name: Name of the tool to execute.
            tool_input: Input dict for the tool.

        Returns:
            JSON string of the tool output.
        """
        try:
            tool = self.tools[tool_name]
            parsed_input = tool.input_model.model_validate(tool_input)
            result = tool.execute(parsed_input)
            return json.dumps(result.model_dump())
        except KeyError:
            return f'Tool {tool_name} not found.'
        except Exception as e:
            return f'Error executing tool {tool_name}: {e!s}'
