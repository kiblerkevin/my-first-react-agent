from agent.base_agent import BaseAgent
from agent.claude_client import ClaudeClient
from agent.context_window import ContextWindow
from tools.fetch_articles_tool import FetchArticlesTool
from tools.fetch_scores_tool import FetchScoresTool

SYSTEM_PROMPT = (
    "You are a Chicago sports news assistant. "
    "When asked about recent Chicago sports news or articles, use the fetch_articles tool to retrieve them. "
    "When asked about scores or game results, use the fetch_scores tool to retrieve them."
)


def main():
    context = ContextWindow(conversation_history=[])
    client = ClaudeClient(system_prompt=SYSTEM_PROMPT)

    fetch_articles_tool = FetchArticlesTool()
    fetch_scores_tool = FetchScoresTool()

    agent = BaseAgent(context=context, claude_client=client)
    agent.tools = {
        fetch_articles_tool.name: fetch_articles_tool,
        fetch_scores_tool.name: fetch_scores_tool
    }

    print("--- Message 1: Articles ---")
    response = agent.send_message("Fetch the latest Chicago sports articles.")
    print(f"\nAgent response:\n{response}\n")

    print("--- Message 2: Scores ---")
    response = agent.send_message("Now fetch the latest Chicago sports scores.")
    print(f"\nAgent response:\n{response}\n")


if __name__ == "__main__":
    main()
