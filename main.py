from workflow.daily_workflow import run_daily_workflow


def main():
    print("--- Running Daily Workflow ---\n")
    result = run_daily_workflow(max_articles_per_team=2)

    print(f"\n--- Workflow Complete ---")
    print(f"Title:         {result['title']}")
    print(f"Teams covered: {result['teams_covered']}")
    print(f"Articles used: {result['article_count']}")
    print(f"Overall score: {result['overall_score']}/10")
    print(f"Email sent:    {result['email_sent']}")
    if result['error']:
        print(f"Error:         {result['error']}")
    print(f"\nAwaiting human approval via email.")
    print(f"Approval server: python server/approval_server.py")


if __name__ == "__main__":
    main()
