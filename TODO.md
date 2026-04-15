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

## Remaining 🔲
8. create_blog_taxonomy — Resolve WordPress category/tag IDs, build mcp_payload for REST API
9. Human approval gate  — Email-based approval flow using APPROVAL_BASE_URL in .env
10. WordPress publish   — POST approved draft to WordPress using credentials in .env
11. Email notification  — Send confirmation email via SMTP config in .env after publishing

## Notes
- Memory/database layer (article deduplication across runs) is deferred
- Embeddings/cosine similarity deferred to memory layer implementation
- Deduplication method: fuzzy string matching on titles using rapidfuzz
- deduplicate_articles runs before summarize_article in the workflow
- refined_excerpt produced during revision loop, not by evaluate_blog_post
- Agent determines whether to proceed to publishing based on overall_score across evaluation runs
- Revision loop kept in main.py (orchestration) rather than as a tool — revisit this design
  decision after the memory layer is implemented

## Design Decisions to Revisit
- [ ] Revision loop as tool vs orchestration — revisit after memory layer is implemented
