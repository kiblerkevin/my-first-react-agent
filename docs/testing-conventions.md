# Testing Conventions

> **TL;DR**: 337 tests, 100% coverage enforced. Use shared fixtures from `conftest.py`. Match existing test class structure. Never remove existing tests.

## Quick Reference

```bash
# Run all tests
./venv/bin/python -m pytest tests/ -x -q

# Run with coverage
./venv/bin/python -m pytest tests/ --cov --cov-report=term-missing

# Run a single test file
./venv/bin/python -m pytest tests/tools/test_fetch_articles.py -x -q
```

## Coverage Requirement

Coverage is enforced at **100%** in `pyproject.toml` and CI. Every new line of code must be tested.

```toml
[tool.coverage.report]
fail_under = 100
```

If a line is truly unreachable, add it to `exclude_lines` in `pyproject.toml` — do not lower the threshold.

## Project Structure

```
tests/
├── conftest.py              # Shared fixtures (autouse + mock data + DB)
├── agent/
│   ├── test_base_agent.py
│   ├── test_claude_client.py
│   ├── test_gemini_adapter.py
│   ├── test_gemini_client.py
│   └── test_revision_agent.py
├── memory/
│   └── test_memory.py
├── server/
│   ├── test_approval_server.py
│   └── test_auth.py
├── tools/
│   ├── test_create_blog_draft.py
│   ├── test_evaluate_blog_post.py
│   ├── test_fetch_articles.py
│   ├── test_fetch_scores.py
│   ├── test_send_approval_email.py
│   ├── test_summarize_article.py
│   └── test_wordpress_publish.py
├── utils/
│   └── ...
└── workflow/
    └── test_daily_workflow.py
```

## Shared Fixtures (`conftest.py`)

### Autouse: EnvProvider

All tests automatically use `EnvProvider` so `monkeypatch.setenv()` and `os.environ` patches work:

```python
@pytest.fixture(autouse=True)
def _use_env_secrets_provider():
    set_provider(EnvProvider())
    yield
    secrets_module._provider_instance = None
```

**Never** call `set_provider()` in individual tests — the autouse fixture handles it.

### Mock Data Fixtures

Use these instead of creating ad-hoc test data:

| Fixture | Description |
|---------|-------------|
| `mock_scores` | 2 completed games + 1 scheduled game |
| `mock_articles` | 6 articles across 3 teams with relevance scores |
| `mock_summaries` | Summarized versions of mock_articles |
| `mock_draft` | Realistic blog draft output dict |
| `mock_evaluation` | Realistic evaluation output dict |
| `mock_claude_json_response` | Factory for ClaudeClient return values |

### Database Fixtures

```python
@pytest.fixture
def tmp_db(tmp_path):
    """Temporary SQLite database, auto-cleaned."""

@pytest.fixture
def memory(tmp_db, monkeypatch):
    """Memory instance with _TestMemory subclass pointed at tmp_db."""
```

The `memory` fixture uses a `_TestMemory` subclass that bypasses config file loading and sets `APPROVAL_SECRET_KEY` in the environment.

## Test Class Structure

### ✅ GOOD — Group by feature, one class per concern

```python
class TestFetchArticles:
    """Tests for the core fetch logic."""

    def test_fetches_from_all_sources(self, ...):
    def test_deduplicates_across_sources(self, ...):

class TestFetchArticlesEdgeCases:
    """Tests for error handling and edge cases."""

    def test_handles_api_timeout(self, ...):
    def test_empty_response_returns_empty_list(self, ...):
```

### ❌ BAD — Flat functions with no grouping

```python
def test_fetch_1():
def test_fetch_2():
def test_fetch_edge():
```

## Mocking Patterns

### External dependencies: `@patch` at the module path

```python
@patch('tools.fetch_articles_tool.NewsAPI_Collector')
@patch('tools.fetch_articles_tool.SerpApiCollector')
def test_fetches_articles(self, mock_serp, mock_news):
    mock_news.return_value.collect.return_value = [...]
```

### Config files: patch `yaml.safe_load` and `builtins.open`

```python
@patch('agent.revision_agent.yaml.safe_load')
@patch('builtins.open')
def test_revision_agent(self, mock_open, mock_yaml):
    mock_yaml.return_value = {'revision_loop': {'criterion_floors': {...}}}
```

### Database: use the `memory` fixture

```python
def test_saves_workflow_run(self, memory):
    run_id = 'wf-test-123'
    memory.create_workflow_run(run_id)
    runs = memory.get_recent_runs(1)
    assert runs[0]['run_id'] == run_id
```

### Server routes: use `_auth_session` context manager

```python
from contextlib import contextmanager

EDITOR_USER = {'email': 'editor@test.com', 'name': 'Editor', 'picture': '', 'role': 'editor'}
ADMIN_USER = {'email': 'admin@test.com', 'name': 'Admin', 'picture': '', 'role': 'admin'}

@contextmanager
def _auth_session(client, user):
    """Inject an authenticated user session into the test client."""
    with client.session_transaction() as sess:
        sess['user'] = user
    yield client

# Usage:
with _auth_session(client, EDITOR_USER):
    response = client.post('/approve/some-token')
    assert response.status_code == 200
```

### Rate limiter: reset between tests

If testing rate-limited endpoints, reset the limiter in your fixture or setup to avoid test pollution.

## Naming Conventions

- Test files: `test_<module_name>.py`
- Test classes: `Test<Feature>` or `Test<Feature>EdgeCases`
- Test methods: `test_<behavior_being_tested>`
- Use descriptive names — `test_tied_scores_prefer_most_recent_draft` not `test_scores_1`

## What NOT to Do

- ❌ Don't remove existing tests unless explicitly asked
- ❌ Don't lower the coverage threshold
- ❌ Don't use `pytest.mark.skip` without a tracked reason
- ❌ Don't create new mock data when a `conftest.py` fixture exists
- ❌ Don't test implementation details — test behavior
- ❌ Don't use `monkeypatch.setattr` on `secrets_module._provider_instance` directly — the autouse fixture handles it
