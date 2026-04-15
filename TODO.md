# Chicago Sports Summarizer — Workflow To-Do List

## Completed ✅
1. fetch_scores         — ESPN API, full score data with expanded fields
2. fetch_articles       — NewsAPI + SerpAPI, per-team queries, relevance scoring, deduplication
3. deduplicate_articles — Fuzzy string matching on titles using rapidfuzz, within-team
4. summarize_article    — BeautifulSoup content fetching, Haiku summarization, event type classification
5. create_blog_draft    — Sonnet drafting, three-section WordPress HTML structure
6. evaluate_blog_post   — Four-criterion scoring (accuracy, completeness, readability, seo), Sonnet
7. Revision loop        — Orchestrated in main.py, for/else loop, per-criterion floors from
                          orchestration.yaml, passes failing criteria as revision_notes back
                          into create_blog_draft, tracks best draft across attempts
8. create_blog_taxonomy — Deterministic, no LLM, Daily Recap + team categories, team + top 4
                          player tags, memory layer with get_or_create pattern, wordpress_id column
9. Human approval gate  — Email-based approval flow with signed tokens, Flask server,
                          APScheduler expiry checker, reject with feedback form
10. WordPress publish   — OAuth2 bearer token, category/tag ID resolution, draft creation
11. Scheduler           — APScheduler cron trigger at 6 AM CT, exponential backoff retry (5 attempts),
                          reusable workflow in workflow/daily_workflow.py

## Future Enhancements 🔮
- [ ] Memory layer — article deduplication across runs, prevent re-summarizing previously seen articles
- [ ] Embeddings/cosine similarity — replace fuzzy title matching with semantic deduplication (depends on memory layer)
- [ ] Revision loop as tool vs orchestration — revisit after memory layer is implemented
- [ ] Email notification — optional confirmation email after human publishes (removed from core workflow)

## Notes
- Memory/database layer started — Memory class in memory.py with category, tag,
  pending approval, and OAuth token CRUD methods
- Article table exists in database.py but nothing writes to it yet
- Deduplication method: fuzzy string matching on titles using rapidfuzz
- deduplicate_articles runs before summarize_article in the workflow
- refined_excerpt produced during revision loop, not by evaluate_blog_post
- Flask server must be started separately: python server/approval_server.py
- Gmail App Password required for SMTP (not regular account password)
- WordPress.com OAuth2 required — run /oauth/start once to authorize
- Scheduler config in config/scheduler.yaml, orchestration config in config/orchestration.yaml

## Design Decisions to Revisit
- [ ] Revision loop as tool vs orchestration — revisit after memory layer is implemented
