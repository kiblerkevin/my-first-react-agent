# Chicago Sports Summarizer — To-Do List

## Remaining Gaps (from prior analysis)

### Functional
- [ ] F2. Minimum content threshold — require N summaries across M teams before drafting
- [x] F3. Stale files cleanup — removed unused `prompts/create_blog_post_prompt.py`, `agent/summary_agent.py`, `agent/evaluator_agent.py`, `utils/message.py`
- [ ] F4. RSS collectors — wire existing RSS feeds into fetch_articles_tool
- [ ] F5. Duplicate approval prevention — check for pending approvals before sending new ones

### Operational
- [x] O2. Health check endpoint — `/health` route on Flask approval server

### Reliability
- [x] R2. Database backup — SQLite `.backup()` API after each workflow, WAL mode enabled, configurable retention
- [ ] R4. Concurrent request protection — atomic approval status updates

### Agent
- [ ] A3. Fallback model configuration — try primary model, fall back to secondary on failure

---

## Completed Features

### CQ. Code Quality Standards ✅

**Implemented:**
- Ruff configured with auto-fix for formatting and import sorting (pyflakes, pycodestyle, isort, bugbear, simplify, pydocstyle)
- mypy strict mode on critical paths (`tools/`, `workflow/`, `memory/`, `agent/`)
- mypy basic mode on remaining code (`server/`, `utils/`, `models/`)
- All configuration in `pyproject.toml`
- Pre-commit hooks (warn-only on commit, blocking on merge via CI)
- GitHub Actions reusable workflows: `ruff.yml` (lint + format), `mypy.yml`, orchestrated by `code-quality.yml`
- Type annotations added to all functions across the entire codebase
- Docstrings enforced on all public classes and methods
- All files pass `ruff check .` and `ruff format --check .`

**Files created:**
- `pyproject.toml` — ruff + mypy + pytest + coverage + mutmut config
- `.pre-commit-config.yaml` — ruff + mypy as warn-only hooks
- `requirements-dev.txt` — ruff, mypy, pre-commit, pytest, pytest-mock, pytest-cov, mutmut, type stubs
- `.github/workflows/code-quality.yml` — orchestrator
- `.github/workflows/ruff.yml` — reusable lint/format workflow
- `.github/workflows/mypy.yml` — reusable type check workflow
- `.github/workflows/tests.yml` — reusable test + coverage workflow

**Commands:**
```bash
ruff check . --fix       # lint with auto-fix
ruff format .            # format
mypy .                   # type check
pre-commit run --all     # run all hooks locally
```

---

### TS. Repeatable Testing Suite ✅

**Implemented:**
- 183 tests, 100% code coverage (enforced in CI)
- All tools tested with mocked LLM and API responses
- Memory layer tested with temporary SQLite databases
- Acceptance tests verify checkpoint order, skip logic, resume, and failure email
- Shared fixtures in `tests/conftest.py` with realistic mock data
- GitHub Actions reusable workflow with configurable coverage threshold

**Structure:**
```
tests/
├── conftest.py                    # shared fixtures, mock factories
├── tools/
│   ├── test_fetch_articles.py     # 7 tests
│   ├── test_fetch_scores.py       # 4 tests
│   ├── test_summarize_article.py  # 5 tests
│   ├── test_create_blog_draft.py  # 8 tests
│   ├── test_evaluate_blog_post.py # 4 tests
│   ├── test_deduplicate_articles.py # 7 tests
│   ├── test_create_blog_taxonomy.py # 2 tests
│   ├── test_send_approval_email.py  # 9 tests
│   └── test_wordpress_publish.py    # 12 tests
├── utils/
│   ├── test_consolidate.py        # 7 tests
│   ├── test_http.py               # 7 tests
│   ├── test_relevance_scoring.py  # 5 tests
│   ├── test_collectors.py         # 12 tests
│   └── test_logger.py             # 1 test
├── memory/
│   └── test_memory.py             # 34 tests
├── agent/
│   ├── test_base_agent.py         # 20 tests
│   ├── test_claude_client.py      # 9 tests
│   └── test_revision_agent.py     # 8 tests
└── workflow/
    └── test_daily_workflow.py     # 8 acceptance tests
```

**Commands:**
```bash
pytest                              # run all tests
pytest --cov --cov-report=html      # coverage report
pytest -m acceptance                # acceptance tests only
```

---

### TS-M. Mutation Testing (blocked by Python 3.14 incompatibility)

**Status:** Configuration complete. Execution blocked by Python 3.14 compatibility issues in both mutmut v2 (deepcopy crash) and v3 (trampoline-based detection doesn't work with mocked imports).

**Configured in `pyproject.toml`:**
```toml
[tool.mutmut]
paths_to_mutate = [
    "utils/consolidate.py",
    "tools/fetch_articles_tool.py",
    "tools/deduplicate_articles_tool.py",
    "tools/evaluate_blog_post_tool.py",
    "memory/memory.py",
]
tests_dir = ["tests"]
```

**Workaround options:**
1. Run mutmut in a Python 3.12 virtualenv (recommended)
2. Wait for mutmut to release a Python 3.14-compatible version
3. Use an alternative tool like `cosmic-ray` or `mutatest`

**To run (in a Python 3.12 env):**
```bash
python3.12 -m venv .venv312
source .venv312/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
mutmut run
mutmut results
```

**Target:** 80%+ mutation kill rate on critical paths.

---

## New Features (not yet started)

### AD. Agent Drift Detection ✅

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

## Priority Order

1. ~~**CQ. Code Quality Standards**~~ ✅
2. ~~**TS. Repeatable Testing Suite**~~ ✅
3. ~~**TS-M. Mutation Testing**~~ — blocked by Python 3.14 (config ready, run in 3.12 env)
4. ~~**AD. Agent Drift Detection**~~ ✅
5. **F5. Duplicate approval prevention** — quick win
6. ~~**O2. Health check endpoint**~~ ✅
7. **A3. Fallback model configuration** — prevents total workflow failure
8. ~~**R2. Database backup**~~ ✅
9. **F4. RSS collectors** — adds free article sources
10. **R4. Concurrent request protection** — edge case for production
11. **F2. Minimum content threshold** — nice-to-have

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
