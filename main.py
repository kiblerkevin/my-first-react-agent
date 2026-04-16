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
        print(f"\nAwaiting human approval via email.")
        print(f"Approval server: python server/approval_server.py")

    print(f"\nTrace details: http://localhost:3000 (Langfuse dashboard)")


if __name__ == "__main__":
    main()
