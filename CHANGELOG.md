# Changelog

All notable changes to this project are documented here.

## 2026-04-28

### Added
- **Tailwind CSS + Alpine.js frontend** — Standalone Tailwind CLI (no Node.js), Alpine.js via CDN. `scripts/install-tailwind.sh`, `scripts/build-css.sh`, `scripts/watch-css.sh`.
- **Template inheritance** — `base.html` (dashboard pages with nav, Alpine.js) and `base_simple.html` (approval pages, minimal). All 10 templates now extend a base.
- **Static JS files** — Extracted `dashboard.js` and `iterations.js` from inline `<script>` blocks into `server/static/js/`.

### Changed
- All inline CSS replaced with Tailwind utility classes across all templates.
- Hamburger nav converted from vanilla JS `onclick` to Alpine.js `x-data`/`@click.outside`.
- Dashboard badge classes use custom Tailwind `@utility` definitions (`badge-success`, `badge-failed`, etc.).

## 2026-04-27

### Fixed
- **Tied-score draft selection bug** — When multiple drafts had the same `overall_score`, `_extract_results` in `revision_agent.py` always picked the first draft (index 0) instead of the most recent revision. Fixed by adding index as a tiebreaker in the `max()` key: `key=lambda i: (score, i)`. This caused the April 27 workflow to send the generic-titled first draft for approval instead of the improved revision.

### Changed
- **Dashboard: API Health** — Replaced single stacked bar chart with dedicated "API Health" section containing per-API pie charts (ESPN, NewsAPI, SerpAPI) plus an LLM Usage stats card.
- **Dashboard: Team Coverage** — Replaced horizontal bar chart with two-column text list sorted by post count descending.
- **Dashboard: LLM endpoint** — Added `/dashboard/api/llm` endpoint and `Memory.get_llm_stats()` method. Shows placeholder message until token tracking is populated in workflow runs.

### Added
- `docs/testing-conventions.md` — Testing patterns, fixtures, mocking conventions
- `docs/prompt-engineering-conventions.md` — Prompt file structure, placeholders, writing guidelines
- `docs/error-handling-conventions.md` — LLM fallback, checkpoint/resume, tool output error patterns
- `CHANGELOG.md` — This file

## 2026-04-26

### Added
- **Navigation menu** — Hamburger-style overlay menu on dashboard and iterations templates with Home, Dashboard, Draft Iterations links. Click-outside-to-close behavior.
- **WordPress integration** — Root redirect `/` → WordPress site. `ProxyFix` middleware for Cloudflare tunnel HTTPS support.
- **`APPROVAL_PORT` separation** — Decoupled port parsing from `APPROVAL_BASE_URL` to support domain-based URLs without ports.

### Fixed
- **`WP_REDIRECT_URI` operator precedence** — Missing parentheses around `or` expression caused incorrect URI construction.

## 2026-04-25

### Added
- **Gemini fallback (A3)** — `agent/gemini_client.py` + `agent/gemini_adapter.py` for automatic fallback on Claude API failures. Haiku→Flash, Sonnet→Pro mapping in `config/llms.yaml`.

### Fixed
- **Revision agent evaluate tool context** — `required_tool_context` was missing `evaluate_blog_post`, causing empty summaries/scores in evaluation calls.

## 2026-04-24

### Added
- **Security (S1-S10)** — Secrets management (Keychain/Env providers), OAuth token encryption (Fernet), Auth0 RBAC, XSS sanitization (bleach), CSRF protection (Flask-WTF), rate limiting (flask-limiter), security headers (CSP, X-Frame-Options), approval token signature+expiry validation, database file permissions 0o600.
- **Dashboard CSP fix** — Updated Content-Security-Policy to allow Chart.js CDN and inline scripts.

## 2026-04-23

### Added
- **Agent drift detection (AD)** — `DriftDetector` class monitoring 7 metrics. Config in `config/drift.yaml`. First-breach-only alerting with recovery emails. Dashboard endpoint at `/dashboard/api/drift`.
- **Database backup (R2)** — SQLite `.backup()` API after each workflow. WAL mode. Configurable retention in `config/database.yaml`.
- **Health check (O2)** — `/health` endpoint returning `{"status": "ok"}`.

## 2026-04-20

### Added
- **Comprehensive logging** — JSON file handler (RotatingFileHandler, 10MB, 5 backups), human-readable console handler, thread-local `run_id` context, per-module log levels. 14-day retention.
- **Testing suite (TS)** — 334 tests with 100% code coverage. Shared fixtures in `tests/conftest.py`.
- **Code quality (CQ)** — Ruff linting/formatting, mypy type checking, pre-commit hooks, GitHub Actions CI workflows.

### Removed
- **Stale files (F3)** — `agent/summary_agent.py`, `agent/evaluator_agent.py`, `utils/message.py`, `prompts/create_blog_post_prompt.py`.
