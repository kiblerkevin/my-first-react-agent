# Copilot Instructions

> **IMPORTANT**: Read `.github/copilot-instructions.md` before making any code changes.

## Quick Reference

| Category | Rule | File |
|----------|------|------|
| Code Style | Follow [Agent Code Standards](docs/agent-code-standards.md) | `docs/agent-code-standards.md` |
| Architecture | Reference [ARCHITECTURE.md](ARCHITECTURE.md) | `ARCHITECTURE.md` |
| Domain Context | See [docs/](docs/) for domain-specific rules | `docs/*.md` |
| Linting | **MUST** pass `ruff check .` before commit | Run locally |
| Type Check | **MUST** pass `mypy .` before commit | Run locally |
| Tests | **MUST** pass `pytest tests/ --cov --cov-fail-under=100` | Run locally |
| CSS Build | Run `bash scripts/build-css.sh` after template changes | Run locally |

## Before Writing Code

1. **Read the relevant domain doc** if modifying:
   - Docker changes → [docs/docker-setup.md](docs/docker-setup.md)
   - Routing/web → [docs/routing-conventions.md](docs/routing-conventions.md)
   - Database code → [docs/flask-sqlalchemy-patterns.md](docs/flask-sqlalchemy-patterns.md)
   - Tests → [docs/testing-conventions.md](docs/testing-conventions.md)
   - Prompts → [docs/prompt-engineering-conventions.md](docs/prompt-engineering-conventions.md)
   - Error handling → [docs/error-handling-conventions.md](docs/error-handling-conventions.md)
   - Recent changes → [CHANGELOG.md](CHANGELOG.md)

2. **Check existing patterns** in the codebase before adding new code

## While Writing Code

### ✅ DO
- Use type hints on all function signatures
- Add docstrings to classes and complex functions
- Follow the good examples in [docs/agent-code-standards.md](docs/agent-code-standards.md)
- Run `ruff check . --fix` before finishing
- Run `mypy .` before finishing

### ❌ DON'T
- Don't write code matching the "BAD" examples in docs
- Don't skip type hints to "save time"
- Don't skip linting/type checking
- Don't add dependencies without approval

## After Writing Code

```bash
# Always run these before committing
ruff check . --fix
mypy .
./venv/bin/python -m pytest tests/ --cov --cov-fail-under=100 -q
```

If any check fails, **fix the errors** before committing. Do not use `--no-verify` or ignore errors.

## Code Quality Checklist

- [ ] Code passes `ruff check .`
- [ ] Code passes `mypy .`
- [ ] Tests pass with 100% coverage
- [ ] CSS rebuilt if templates changed (`bash scripts/build-css.sh`)
- [ ] New functions have docstrings
- [ ] New classes have docstrings
- [ ] Follows patterns from [docs/agent-code-standards.md](docs/agent-code-standards.md)
- [ ] No TODO/FIXME comments left behind (unless tracking a known issue)
- [ ] CHANGELOG.md updated if user-facing behavior changed

## Questions?

- Architecture questions → [ARCHITECTURE.md](ARCHITECTURE.md)
- Code style questions → [docs/agent-code-standards.md](docs/agent-code-standards.md)
- Domain questions → See files in [docs/](docs/)