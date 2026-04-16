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
                 force_first_tool: str = None):
        self.claude_client = claude_client
        self.context = context
        self.tools = {}
        self.max_tool_calls = max_tool_calls
        self.tool_call_count = 0
        self.force_first_tool = force_first_tool

    def send_message(self, user_message: str) -> str:
        self.context.add(UserMessage(content=user_message))
        response = self.act()
        self.context.add(AssistantMessage(content=response))
        return response
    
    def act(self) -> str:
        if self.max_tool_calls and self.tool_call_count >= self.max_tool_calls:
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

                    tool_use = ToolUse(id=str(tool_use_id), name=content_block.name, input=content_block.input)
                    tool_use_msg = ToolUseMessage(content=[tool_use])
                    self.context.add(tool_use_msg)

                    tool_result_response = self._execute_tool(tool_use.name, tool_use.input)
                    self.tool_call_count += 1
                    logger.info(f"Tool call {self.tool_call_count}/{self.max_tool_calls or '∞'}: {tool_use.name}")

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
