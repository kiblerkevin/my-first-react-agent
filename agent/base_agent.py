import json

from agent.claude_client import ClaudeClient
from agent.context_window import ContextWindow
from agent.context_window import (
    ContextWindow,
    UserMessage,
    AssistantMessage,
    ToolUse,
    ToolUseMessage,
    ToolResult,
    ToolResultMessage
)
from typing import List, Dict
from utils.logger.logger import setup_logger

logger = setup_logger(__name__)


class BaseAgent:
    def __init__(self,
                 context: ContextWindow,
                 claude_client: ClaudeClient,
                 max_tool_calls: int = None,
                 force_first_tool: str = None,
                 required_tool_context: dict = None,
                 revision_tracking: dict = None):
        self.claude_client = claude_client
        self.context = context
        self.tools = {}
        self.max_tool_calls = max_tool_calls
        self.tool_call_count = 0
        self.force_first_tool = force_first_tool

        # Rec 2/3: required fields to inject into tool inputs if the LLM omits them
        # Format: {"tool_name": {"field_name": value, ...}}
        self.required_tool_context = required_tool_context or {}

        # Rec 4/5: revision tracking config
        # Format: {"draft_tool": "create_blog_draft", "evaluate_tool": "evaluate_blog_post"}
        self._revision_config = revision_tracking
        self._last_draft_output = None
        self._last_eval_suggestions = None
        self._last_tool_name = None
        self._limit_extended = False

    def send_message(self, user_message: str) -> str:
        self.context.add(UserMessage(content=user_message))
        response = self.act()
        self.context.add(AssistantMessage(content=response))
        return response
    
    def act(self) -> str:
        if self.max_tool_calls and self.tool_call_count >= self.max_tool_calls:
            # Rec 5: extend limit by 1 if last tool was a draft so agent can evaluate
            if (self._revision_config
                    and self._last_tool_name == self._revision_config.get('draft_tool')
                    and not self._limit_extended):
                self._limit_extended = True
                self.max_tool_calls += 1
                logger.warning(
                    f"Extended tool call limit to {self.max_tool_calls} "
                    f"to allow final evaluation after draft."
                )
            else:
                logger.warning(f"Tool call limit reached ({self.max_tool_calls}). Stopping agent.")
                return "Tool call limit reached. Returning best available result."

        # Force tool use on first call if configured
        tool_choice = None
        if self.force_first_tool and self.tool_call_count == 0:
            tool_choice = {"type": "tool", "name": self.force_first_tool}

        response = self.claude_client.send_messages_with_tools(
            messages=[msg.model_dump() for msg in self.context.conversation_history],
            tools=[{
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema
                } for tool in self.tools.values()],
            tool_choice=tool_choice
        )
        
        tool_use_id = 1
        
        # Check if response contains tool use blocks
        has_tool_use = any(
            getattr(block, 'type', None) == 'tool_use'
            for block in (response.content or [])
        )

        if has_tool_use:
            for content_block in response.content:
                if content_block.type == "tool_use":
                    if self.max_tool_calls and self.tool_call_count >= self.max_tool_calls:
                        logger.warning(f"Tool call limit reached mid-response ({self.max_tool_calls}). Stopping.")
                        tool_result = ToolResult(
                            tool_use_id=str(tool_use_id),
                            content="Tool call limit reached. Please return your best result now.",
                            is_error=True
                        )
                        tool_result_message = ToolResultMessage(content=[tool_result])
                        self.context.add(tool_result_message)
                        return self.act()

                    tool_input = dict(content_block.input)

                    # Rec 2/3: inject missing required context and log warnings
                    tool_input = self._inject_required_context(content_block.name, tool_input)

                    # Rec 4: inject revision context if this is a subsequent draft call
                    tool_input = self._inject_revision_context(content_block.name, tool_input)

                    tool_use = ToolUse(id=str(tool_use_id), name=content_block.name, input=tool_input)
                    tool_use_msg = ToolUseMessage(content=[tool_use])
                    self.context.add(tool_use_msg)

                    tool_result_response = self._execute_tool(tool_use.name, tool_use.input)
                    self.tool_call_count += 1
                    self._last_tool_name = content_block.name
                    logger.info(f"Tool call {self.tool_call_count}/{self.max_tool_calls or '∞'}: {tool_use.name}")

                    # Rec 4: track draft/eval outputs for revision injection
                    self._track_revision_output(content_block.name, tool_result_response)

                    tool_result = ToolResult(tool_use_id=str(tool_use_id), content=tool_result_response, is_error=False)
                    tool_result_message = ToolResultMessage(content=[tool_result])
                    self.context.add(tool_result_message)
                    
                    tool_use_id += 1

            return self.act()
        
        # Extract text from response, handling mixed content blocks
        for block in (response.content or []):
            if hasattr(block, 'text'):
                return block.text
        return ""

    def _inject_required_context(self, tool_name: str, tool_input: dict) -> dict:
        """Rec 2/3: Merge required context into tool input, warn on missing fields."""
        required = self.required_tool_context.get(tool_name, {})
        for field, value in required.items():
            if not tool_input.get(field):
                logger.warning(
                    f"LLM omitted required field '{field}' for {tool_name} — injecting from context."
                )
                tool_input[field] = value
        return tool_input

    def _inject_revision_context(self, tool_name: str, tool_input: dict) -> dict:
        """Rec 4: Auto-inject current_draft and revision_notes on subsequent draft calls."""
        if not self._revision_config:
            return tool_input

        draft_tool = self._revision_config.get('draft_tool')
        if tool_name != draft_tool or not self._last_draft_output:
            return tool_input

        if not tool_input.get('current_draft') and self._last_draft_output.get('content'):
            logger.warning(
                f"LLM omitted 'current_draft' on revision call — injecting previous draft."
            )
            tool_input['current_draft'] = self._last_draft_output['content']

        if not tool_input.get('revision_notes') and self._last_eval_suggestions:
            logger.warning(
                f"LLM omitted 'revision_notes' on revision call — injecting evaluation suggestions."
            )
            tool_input['revision_notes'] = self._last_eval_suggestions

        return tool_input

    def _track_revision_output(self, tool_name: str, result_json: str):
        """Rec 4: Store draft/eval outputs for revision injection on subsequent calls."""
        if not self._revision_config:
            return

        try:
            result = json.loads(result_json)
        except (json.JSONDecodeError, TypeError):
            return

        if tool_name == self._revision_config.get('draft_tool'):
            if 'title' in result and 'content' in result:
                self._last_draft_output = result

        elif tool_name == self._revision_config.get('evaluate_tool'):
            if 'improvement_suggestions' in result:
                self._last_eval_suggestions = result['improvement_suggestions']

    def _execute_tool(self, tool_name: str, tool_input: dict) -> str:
        try:
            tool = self.tools[tool_name]
            parsed_input = tool.input_model.model_validate(tool_input)
            result = tool.execute(parsed_input)
            return json.dumps(result.model_dump())
        except KeyError:
            return f"Tool {tool_name} not found."
        except Exception as e:
            return f"Error executing tool {tool_name}: {str(e)}"
    
    def _print_tool_use(self, tool_use: ToolUse):
        print(
            f"Tool: {tool_use.name}\nInput: {tool_use.input}"
        )
        
    def _print_tool_result(self, tool_result: ToolResult):
        print(
            f"Tool Result for Tool Use ID {tool_result.tool_use_id}:\n{tool_result.content}"
        )
