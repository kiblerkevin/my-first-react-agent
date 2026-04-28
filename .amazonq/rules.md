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

**You MUST fix all errors before completing the task.**

## Domain-Specific Rules

- Docker changes → [../docs/docker-setup.md](../docs/docker-setup.md)
- Routing changes → [../docs/routing-conventions.md](../docs/routing-conventions.md)
- Database changes → [../docs/flask-sqlalchemy-patterns.md](../docs/flask-sqlalchemy-patterns.md)

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