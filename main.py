import sys
from workflow.daily_workflow import run_daily_workflow


def main():
    resume_run_id = None
    if '--resume' in sys.argv:
        idx = sys.argv.index('--resume')
        if idx + 1 < len(sys.argv):
            resume_run_id = sys.argv[idx + 1]

    if resume_run_id:
        print(f"--- Resuming Workflow: {resume_run_id} ---\n")
    else:
        print("--- Running Daily Workflow ---\n")

    result = run_daily_workflow(max_articles_per_team=2, resume_run_id=resume_run_id)

    print(f"\nRun ID: {result['run_id']}")

    if result.get('skipped'):
        print(f"Status: Skipped")
        print(f"Reason: {result['skip_reason']}")
    else:
        print(f"Status: Complete")
        print(f"Title:         {result['title']}")
        print(f"Teams covered: {result['teams_covered']}")
        print(f"Articles used: {result['article_count']}")
        print(f"Overall score: {result['overall_score']}/10")
        print(f"Email sent:    {result['email_sent']}")
        if result.get('error'):
            print(f"Error:         {result['error']}")

    # Token usage
    print(f"\n--- Token Usage ---")
    usage_by_tool = result.get('usage_by_tool', {})
    for tool_name, usage in usage_by_tool.items():
        print(
            f"  {tool_name:<22} "
            f"{usage['input_tokens']:>7} in / {usage['output_tokens']:>7} out "
            f"({usage['call_count']} calls) ${usage['estimated_cost']:.4f}"
        )
    print(f"  {'TOTAL':<22} "
          f"{result.get('total_input_tokens', 0):>7} in / {result.get('total_output_tokens', 0):>7} out "
          f"${result.get('estimated_cost', 0):.4f}")

    if not result.get('skipped'):
        print(f"\nAwaiting human approval via email.")
        print(f"Approval server: python server/approval_server.py")


if __name__ == "__main__":
    main()
