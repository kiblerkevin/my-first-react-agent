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
9. Human approval gate  — Email-based approval flow:
                          - send_approval_email tool generates signed token, persists PendingApproval
                            to DB, sends rendered HTML email with approve/reject buttons
                          - Flask approval server (server/approval_server.py) handles callbacks
                          - APScheduler background thread auto-archives expired approvals (24h)
                          - Reject flow includes optional feedback form

## Remaining 🔲
10. WordPress publish   — POST approved draft to WordPress using credentials in .env;
                          called from Flask server on approval callback; resolve wordpress_id
                          for categories and tags via WordPress REST API
11. Email notification  — Send confirmation email via SMTP after publishing

## Notes
- Memory/database layer started — Memory class in memory.py with category, tag, and
  pending approval CRUD methods
- Full memory layer (article deduplication across runs) still deferred
- Embeddings/cosine similarity deferred to memory layer implementation
- Deduplication method: fuzzy string matching on titles using rapidfuzz
- deduplicate_articles runs before summarize_article in the workflow
- refined_excerpt produced during revision loop, not by evaluate_blog_post
- Agent determines whether to proceed to publishing based on overall_score across evaluation runs
- Revision loop kept in main.py (orchestration) rather than as a tool
- Flask server must be started separately: python server/approval_server.py
- Gmail App Password required for SMTP (not regular account password)

## Design Decisions to Revisit
- [ ] Revision loop as tool vs orchestration — revisit after memory layer is implemented
