# Chicago Sports Summarizer — Workflow To-Do List

## Completed ✅
1. fetch_scores         — ESPN API, full score data with expanded fields
2. fetch_articles       — NewsAPI + SerpAPI, per-team queries, relevance scoring, deduplication
3. summarize_article    — BeautifulSoup content fetching, Haiku summarization, event type classification
4. create_blog_draft    — Sonnet drafting, three-section WordPress HTML structure

## Remaining 🔲
5. deduplicate_articles — Fuzzy string matching on titles using rapidfuzz, runs before summarize_article
6. evaluate_blog_post   — Score draft on quality criteria, refine SEO excerpt, flag issues
7. Human approval gate  — Email-based approval flow using APPROVAL_BASE_URL in .env
8. create_blog_taxonomy — Resolve WordPress category/tag IDs, build mcp_payload for REST API
9. WordPress publish    — POST approved draft to WordPress using credentials in .env
10. Email notification  — Send confirmation email via SMTP config in .env after publishing

## Notes
- Memory/database layer (article deduplication across runs) is deferred
- Embeddings/cosine similarity deferred to memory layer implementation
- Deduplication method: fuzzy string matching on titles using rapidfuzz
- deduplicate_articles runs before summarize_article in the workflow
