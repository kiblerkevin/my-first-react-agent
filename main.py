import json

from agent.base_agent import BaseAgent
from agent.claude_client import ClaudeClient
from agent.context_window import ContextWindow
from tools.fetch_articles_tool import FetchArticlesTool
from tools.fetch_scores_tool import FetchScoresTool
from tools.summarize_article_tool import SummarizeArticleTool
from models.inputs.summarize_article_input import SummarizeArticleInput

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
    summarize_tool = SummarizeArticleTool()

    agent = BaseAgent(context=context, claude_client=client)
    agent.tools = {
        fetch_articles_tool.name: fetch_articles_tool,
        fetch_scores_tool.name: fetch_scores_tool
    }

    print("--- Step 1: Fetch Articles ---")
    response = agent.send_message("Fetch the latest Chicago sports articles.")
    print(f"\nAgent response:\n{response}\n")

    print("--- Step 2: Fetch Scores ---")
    response = agent.send_message("Now fetch the latest Chicago sports scores.")
    print(f"\nAgent response:\n{response}\n")

    print("--- Step 3: Summarize Top Article ---")
    articles = fetch_articles_tool.execute(
        fetch_articles_tool.input_model(force_refresh=False)
    ).articles

    if articles:
        top = max(articles, key=lambda a: a.get('relevance_score', 0))
        print(f"Summarizing: [{top.get('relevance_score')}] [{top.get('team')}] {top.get('title')}")
        print(f"URL: {top.get('url')}\n")

        summary_result = summarize_tool.execute(SummarizeArticleInput(
            url=top['url'],
            title=top['title'],
            team=top['team'],
            published_at=top.get('publishedAt', '')
        ))

        print(f"Summary:          {summary_result.summary}")
        print(f"Event type:       {summary_result.event_type}")
        print(f"Players:          {summary_result.players_mentioned}")
        print(f"Is relevant:      {summary_result.is_relevant}")
    else:
        print("No articles returned.")


if __name__ == "__main__":
    main()
