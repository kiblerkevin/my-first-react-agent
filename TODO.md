# Chicago Sports Summarizer — To-Do List

## Remaining Gaps (from prior analysis)

### Functional
- [ ] F2. Minimum content threshold — require N summaries across M teams before drafting
- [ ] F3. Stale files cleanup — remove unused prompts/create_blog_post_prompt.py, empty agent stubs
- [ ] F4. RSS collectors — wire existing RSS feeds into fetch_articles_tool
- [ ] F5. Duplicate approval prevention — check for pending approvals before sending new ones

### Operational
- [ ] O2. Health check endpoint — /health route on Flask server

### Reliability
- [ ] R2. Database backup — periodic SQLite backup or WAL mode
- [ ] R4. Concurrent request protection — atomic approval status updates

### Agent
- [ ] A3. Fallback model configuration — try primary model, fall back to secondary on failure

---

## New Features

### CQ. Code Quality Standards

**Tool:** Ruff (linting + formatting) + mypy (type checking)

**Scope:**
- Ruff configured with auto-fix for formatting and import sorting
- Ruff linting rules: pyflakes, pycodestyle, isort, bugbear, simplify
- mypy strict mode on critical paths (tools/, workflow/, memory/, agent/)
- mypy basic mode on remaining code (server/, utils/, models/)
- Configuration in `pyproject.toml`
- Pre-commit hook for local enforcement
- Single command: `ruff check . --fix && ruff format . && mypy .`

**Files to create/modify:**
- `pyproject.toml` — ruff + mypy configuration
- `.pre-commit-config.yaml` — pre-commit hooks
- `requirements-dev.txt` — dev dependencies (ruff, mypy, pre-commit)
- Fix all existing lint/type errors across the codebase

---

### TS. Repeatable Testing Suite

**Tools:** pytest + pytest-mock + pytest-cov + mutmut

**Unit Tests (all tools):**
- Each tool gets a test file in `tests/tools/test_<tool_name>.py`
- LLM-calling tools use mocked `ClaudeClient.send_message` responses
- API-calling tools use mocked `requests`/`rate_limited_request` responses
- Memory layer tests use a temporary in-memory SQLite database
- Consolidation, scoring, deduplication utilities get dedicated test files

**Acceptance Tests:**
- Full workflow end-to-end with all external calls mocked
- Verifies: correct step order, checkpoint creation, skip logic, failure email
- Uses fixture data representing a realistic day's articles and scores

**Mutation Testing:**
- `mutmut` configured on critical paths:
  - `utils/consolidate.py`
  - `tools/fetch_articles_tool.py` (scoring logic)
  - `tools/deduplicate_articles_tool.py`
  - `tools/evaluate_blog_post_tool.py` (parsing logic)
  - `memory/memory.py` (query methods)
- Target: 80%+ mutation kill rate on critical paths

**Structure:**
```
tests/
├── conftest.py              # shared fixtures, mock factories
├── tools/
│   ├── test_fetch_articles.py
│   ├── test_fetch_scores.py
│   ├── test_summarize_article.py
│   ├── test_create_blog_draft.py
│   ├── test_evaluate_blog_post.py
│   ├── test_deduplicate_articles.py
│   ├── test_create_blog_taxonomy.py
│   ├── test_send_approval_email.py
│   └── test_wordpress_publish.py
├── utils/
│   ├── test_consolidate.py
│   ├── test_http.py
│   └── test_relevance_scoring.py
├── memory/
│   └── test_memory.py
├── agent/
│   ├── test_base_agent.py
│   └── test_revision_agent.py
├── workflow/
│   └── test_daily_workflow.py  # acceptance tests
└── mutations/
    └── mutmut_config.py
```

**Commands:**
- `pytest` — run all unit + acceptance tests
- `pytest --cov=. --cov-report=html` — coverage report
- `mutmut run --paths-to-mutate=utils/consolidate.py,tools/deduplicate_articles_tool.py` — mutation testing

---

### AD. Agent Drift Detection

**Approach:** Active monitoring with configurable thresholds, scheduled check, email alert on drift.

**Metrics monitored:**

| Metric | Default Threshold | Window |
|--------|-------------------|--------|
| Average overall score | < 7.0 | Last 5 runs |
| Consecutive failures | ≥ 3 | Sequential |
| Average revision tool calls | > 5 | Last 5 runs |
| Completeness score | < 6.0 | 3 consecutive runs |
| Accuracy score | < 7.0 | 2 consecutive runs |
| Approval rejection rate | > 50% | Last 7 runs |
| Consecutive no-news skips | ≥ 3 | Sequential |

**Implementation:**
- `config/drift.yaml` — configurable thresholds per metric
- `utils/drift_detector.py` — `DriftDetector` class that queries the database and evaluates each metric against its threshold
- `memory/memory.py` — add `get_drift_metrics()` method returning all needed data in one query
- `server/approval_server.py` — add drift check to the APScheduler (runs after each workflow, or hourly)
- Drift alert email sent to `ERROR_EMAIL_TO` with: which metrics are drifting, current values vs thresholds, last N run scores, suggested actions
- Dashboard integration: `/dashboard/api/drift` endpoint returning current drift status, displayed as a warning banner on the dashboard when active

**Alert email format:**
- Subject: `[Drift Alert] Chicago Sports Recap — {metric_name}`
- Body: metric name, current value, threshold, trend over last N runs, suggested action (e.g. "Review evaluation prompts" or "Check API connectivity")

---

## AI-Suggested Priority Order

Based on production impact, dependency order, and effort:

1. **CQ. Code Quality Standards** — do this first because it establishes the foundation for all future code. Every subsequent feature benefits from linting and type checking catching bugs early. Low effort, high long-term value.

2. **TS. Repeatable Testing Suite** — do this second because it gives you confidence that existing features work correctly before adding more. The mocked test infrastructure also makes it safe to refactor. Medium effort, critical for reliability.

3. **AD. Agent Drift Detection** — do this third because it's the early warning system for production issues. Once tests confirm the code is correct, drift detection confirms the *outputs* stay correct over time. Depends on having enough historical data (which accumulates daily).

4. **F5. Duplicate approval prevention** — quick win, prevents user confusion when approvals overlap.

5. **O2. Health check endpoint** — one-line route, needed for any monitoring/load balancer setup.

6. **A3. Fallback model configuration** — prevents total workflow failure on Anthropic outages.

7. **R2. Database backup** — protects against data loss as the system accumulates history.

8. **F4. RSS collectors** — adds free article sources, improves content coverage.

9. **R4. Concurrent request protection** — edge case but important for production correctness.

10. **F2. Minimum content threshold** — nice-to-have, prevents thin posts on slow news days.

11. **F3. Stale files cleanup** — housekeeping, zero production impact.

---

## Design Decisions (from prior work)

- Revision loop managed by RevisionAgent (Phase 1 of agent self-reflection)
- Memory access via pre-loaded context; query_memory tool deferred to Phase 2 (full workflow agent)
- Embeddings/cosine similarity deferred until memory layer matures
- Dashboard authentication deferred — keep routes unauthenticated on localhost, add auth to dashboard blueprint when needed

## Notes

- See RUNBOOK.md for startup checklist and troubleshooting
- Scheduler config: config/scheduler.yaml | Orchestration config: config/orchestration.yaml
- Langfuse dashboard: http://localhost:3000 | Approval server: http://localhost:5000
- Admin dashboard: http://localhost:5000/dashboard | Iterations: http://localhost:5000/dashboard/iterations
