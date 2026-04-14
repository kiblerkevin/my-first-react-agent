from agent.base_agent import BaseAgent
from agent.claude_client import ClaudeClient
from agent.context_window import ContextWindow
from tools.fetch_articles_tool import FetchArticlesTool

SYSTEM_PROMPT = (
    "You are a Chicago sports news assistant. "
    "When asked about recent Chicago sports news or articles, use the fetch_articles tool to retrieve them."
)


def main():
    context = ContextWindow(conversation_history=[])
    client = ClaudeClient(system_prompt=SYSTEM_PROMPT)

    fetch_tool = FetchArticlesTool()

    agent = BaseAgent(context=context, claude_client=client)
    agent.tools = {fetch_tool.name: fetch_tool}

    print("Sending message to agent...")
    response = agent.send_message("Fetch the latest Chicago sports articles.")
    print(f"\nAgent response:\n{response}")


if __name__ == "__main__":
    main()
