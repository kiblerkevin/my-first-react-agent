# Chicago Sports Summarizer — Workflow To-Do List

## Completed ✅
1. fetch_scores         — ESPN API, full score data with expanded fields
2. fetch_articles       — NewsAPI + SerpAPI, per-team queries, relevance scoring, deduplication
3. deduplicate_articles — Fuzzy string matching on titles using rapidfuzz, within-team
4. summarize_article    — BeautifulSoup content fetching, Haiku summarization, event type classification
5. create_blog_draft    — Sonnet drafting, three-section WordPress HTML structure
6. evaluate_blog_post   — Four-criterion scoring (accuracy, completeness, readability, seo), Sonnet

## Remaining 🔲
7. Revision loop        — Orchestrated in main.py; passes improvement_suggestions back into
                          create_blog_draft, max 3 retries, configurable score threshold
8. Human approval gate  — Email-based approval flow using APPROVAL_BASE_URL in .env
9. create_blog_taxonomy — Resolve WordPress category/tag IDs, build mcp_payload for REST API
10. WordPress publish   — POST approved draft to WordPress using credentials in .env
11. Email notification  — Send confirmation email via SMTP config in .env after publishing

## Notes
- Memory/database layer (article deduplication across runs) is deferred
- Embeddings/cosine similarity deferred to memory layer implementation
- Deduplication method: fuzzy string matching on titles using rapidfuzz
- deduplicate_articles runs before summarize_article in the workflow
- refined_excerpt is produced during the revision loop, not by evaluate_blog_post
- Agent determines whether to proceed to publishing based on overall_score across evaluation runs
- Revision loop kept in main.py (orchestration) rather than as a tool — revisit this design
  decision after the memory layer is implemented, at which point the agent may have enough
  context to make smarter revision decisions than a simple threshold check

## Open Questions
- [ ] Should MIN_SCORE threshold and MAX_RETRIES be hardcoded in main.py or configurable?
- [ ] Should revision trigger on overall_score only, or also on individual criterion floors?
