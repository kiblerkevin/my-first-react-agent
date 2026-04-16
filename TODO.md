# Chicago Sports Summarizer — Workflow To-Do List

## Completed ✅
1. fetch_scores             — ESPN API, expanded fields, yesterday + today date range
2. fetch_articles           — NewsAPI + SerpAPI, per-team queries, relevance scoring, per-source trimming
3. deduplicate_articles     — Fuzzy string matching (rapidfuzz), within-team
4. summarize_article        — BeautifulSoup + Haiku, event type classification, summary caching
5. create_blog_draft        — Sonnet, three-section WordPress HTML, revision support
6. evaluate_blog_post       — Sonnet, four-criterion scoring (accuracy, completeness, readability, seo)
7. Revision loop            — Orchestrated, per-criterion floors, best-draft tracking
8. create_blog_taxonomy     — Deterministic, Daily Recap + team categories, top 4 player tags
9. Human approval gate      — Signed tokens, Flask server, APScheduler expiry, reject with feedback
10. WordPress publish       — OAuth2, category/tag ID resolution, draft creation
11. Scheduler               — APScheduler cron (6 AM CT), exponential backoff retry
12. Memory layer            — Article dedup across runs, summary caching, blog draft + evaluation persistence
13. Rejection feedback loop — Loads most recent rejection feedback into drafter and evaluator prompts

## Functional Gaps 🔧
- [x] F1. No-news-day handling — skip drafting when no new articles exist
- [ ] F2. Minimum content threshold — require N summaries across M teams before drafting
- [ ] F3. Stale files cleanup — remove unused prompts/create_blog_post_prompt.py, empty agent stubs
- [ ] F4. RSS collectors — wire existing RSS feeds into fetch_articles_tool
- [ ] F5. Duplicate approval prevention — check for pending approvals before sending new ones

## Operational Gaps 📊
- [x] O1. Workflow run tracking — WorkflowRun table with run_id, timing, status, steps completed
- [ ] O2. Health check endpoint — /health route on Flask server
- [x] O3. Token cost tracking — replaced with Langfuse observability (A1)
- [x] O4. Log rotation — purge log files older than retention window
- [x] O5. OAuth token validation — verify token before publish, handle revocation

## Reliability Gaps 🛡️
- [x] R1. Per-step error recovery — checkpoint completed steps, resume from last success
- [ ] R2. Database backup — periodic SQLite backup or WAL mode
- [x] R3. API rate limiting — throttle/retry on 429 responses per API
- [ ] R4. Concurrent request protection — atomic approval status updates

## Missing Agent Features 🤖
- [x] A1. Langfuse observability — @observe decorators on workflow and LLM calls, Docker self-hosted
- [ ] A2. Agent self-reflection — let BaseAgent reason about intermediate results
- [ ] A3. Fallback model configuration — try primary model, fall back to secondary on failure

## Design Decisions to Revisit
- [ ] Revision loop as tool vs orchestration — revisit after agent self-reflection (A2)
- [ ] Embeddings/cosine similarity — revisit after memory layer matures

## Notes
- See RUNBOOK.md for startup checklist and troubleshooting
- Scheduler config: config/scheduler.yaml | Orchestration config: config/orchestration.yaml
- Langfuse dashboard: http://localhost:3000 | Approval server: http://localhost:5000
