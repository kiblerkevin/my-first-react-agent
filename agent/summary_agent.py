from agent.claude_client import ClaudeClient
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

class SummaryAgent:
    def __init__(self,
                 context: ContextWindow,
                 claude_client: ClaudeClient):
        self.claude_client = claude_client
        self.context = context
        self.tools = []  # Define any tools the agent might use here

    def send_message(self, user_message: str) -> str:
        self.context.add(UserMessage(content=user_message))
        response = self.act()
        self.context.add(AssistantMessage(content=response))
        return response
    
    def act(self) -> str:
        response = self.claude_client.send_messages_with_tools(
            messages=[msg.model_dump() for msg in self.context.conversation_history],
            tools=[tool.model_dump() for tool in self.tools]
        )
        
        tool_use_id = 1
        
        if response.stop_reason == "tool_use":
            # Add tool use to context
            for content_block in response.content:
                if content_block.type == "tool_use":
                    # Add tool use message
                    tool_use = ToolUse(id=str(tool_use_id), name=content_block.name, input=content_block.input)
                    tool_use_msg = ToolUseMessage(content=[tool_use])
                    self.context.add(tool_use_msg)

                    # Display tool use in orange box
                    # self._print_tool_use(tool_use)
                    tool_result_response = self._execute_tool(tool_use.name, tool_use.input)

                    # Add tool result to context
                    tool_result = ToolResult(tool_use_id=str(tool_use_id), content=tool_result_response, is_error=False)
                    tool_result_message = ToolResultMessage(content=[tool_result])
                    self.context.add(tool_result_message)

                    # Display tool result in red box
                    # self._print_tool_result(tool_result)
                    
                    tool_use_id += 1
                    

            # Make another API call to continue the conversation
            return self.act()

        return response.content[0].text if response.content else ""
    
    def _execute_tool(self, tool_name: str, tool_input: dict) -> str:
        try:
            pass
        except Exception as e:
            return f"Error executing tool {tool_name}: {str(e)}"

    def summarize_articles(self, source_articles: List[Dict[str, str]]) -> Dict[str, str]:
        # Implementation for summarizing source articles
        pass