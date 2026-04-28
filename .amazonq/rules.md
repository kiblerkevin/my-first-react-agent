# Amazon Q Agent Rules

> **IMPORTANT**: Read these rules before making any code changes.

## Pre-Code Requirements

1. **Read architecture**: [ARCHITECTURE.md](../ARCHITECTURE.md)
2. **Read code standards**: [docs/agent-code-standards.md](../docs/agent-code-standards.md)
3. **Check domain docs**: See [../docs/](../docs/) directory

## Code Quality Gates

| Check | Command | Required |
|-------|---------|----------|
| Linting | `ruff check . --fix` | ✅ Yes |
| Type Check | `mypy .` | ✅ Yes |
| Tests | `./venv/bin/python -m pytest tests/ --cov --cov-fail-under=100 -q` | ✅ Yes |
| CSS Build | `bash scripts/build-css.sh` | ✅ After template changes |

**You MUST fix all errors and maintain 100% test coverage before completing the task.**

## Domain-Specific Rules

- Docker changes → [../docs/docker-setup.md](../docs/docker-setup.md)
- Routing changes → [../docs/routing-conventions.md](../docs/routing-conventions.md)
- Database changes → [../docs/flask-sqlalchemy-patterns.md](../docs/flask-sqlalchemy-patterns.md)
- Test changes → [../docs/testing-conventions.md](../docs/testing-conventions.md)
- Prompt changes → [../docs/prompt-engineering-conventions.md](../docs/prompt-engineering-conventions.md)
- Error handling → [../docs/error-handling-conventions.md](../docs/error-handling-conventions.md)
- Recent changes → [../CHANGELOG.md](../CHANGELOG.md)

## Frontend Rules

- Templates use **Jinja2 inheritance**: `base.html` (dashboard pages) or `base_simple.html` (approval pages)
- CSS: **Tailwind CSS** via standalone CLI — use utility classes, not inline styles
- Interactivity: **Alpine.js** (`x-data`, `x-show`, `@click`) — no jQuery, no vanilla `onclick` attributes
- After editing templates: run `bash scripts/build-css.sh` to regenerate `output.css`
- During development: run `bash scripts/watch-css.sh` for auto-rebuild on changes
- Chart.js is loaded via CDN in `{% block head %}` only on pages that need it

## Code Patterns

Follow the **GOOD** examples in [docs/agent-code-standards.md](../docs/agent-code-standards.md). Avoid the **BAD** examples.

### Required Patterns

- All functions must have type hints
- All public classes must have docstrings
- All complex functions must have docstrings
- Use Pydantic for tool input/output (see `tools/base_tool.py`)

### Prohibited Patterns

- ❌ Functions without type hints
- ❌ Classes without docstrings
- ❌ Magic numbers (use constants)
- ❌ TODO/FIXME comments (unless tracking known issues)

## Workflow

1. Read relevant domain docs
2. Check existing code patterns
3. Write code following standards
4. Run `ruff check . --fix`
5. Run `mypy .`
6. Fix any errors
7. Verify against code standards doc