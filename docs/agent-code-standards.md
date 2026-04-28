# Agent Code Standards

> **TL;DR**: Write code a human can read, maintain, and debug in 6 months. Not code that works today but becomes technical debt tomorrow.

## Why This Document Exists

AI agents tend to write:
- Clever one-liners that are hard to debug
- Missing documentation
- Inconsistent patterns
- Code that works but isn't maintainable

This document provides **explicit examples** of what to do and what to avoid.

---

## Type Hints

### ✅ GOOD - Explicit types everywhere

```python
def calculate_score(home_points: int, away_points: int, is_overtime: bool) -> int:
    """Calculate the final score with overtime adjustment.
    
    Args:
        home_points: Points scored by home team.
        away_points: Points scored by away team.
        is_overtime: Whether the game went into overtime.
    
    Returns:
        Final score differential (home - away).
    """
    base_score = home_points - away_points
    if is_overtime:
        return base_score + 3  # Overtime bonus
    return base_score
```

### ❌ BAD - Missing or partial types

```python
# Missing return type
def calculate_score(home_points, away_points, is_overtime):
    base_score = home_points - away_points
    if is_overtime:
        return base_score + 3
    return base_score
```

---

## Docstrings

### ✅ GOOD - Complete docstring with Args, Returns, Raises

```python
def fetch_articles(sport: str, limit: int = 10) -> list[Article]:
    """Fetch recent articles for a given sport.
    
    Queries the external article API and returns parsed Article objects.
    Handles rate limiting automatically with exponential backoff.
    
    Args:
        sport: The sport category (e.g., "nba", "mlb", "nfl").
        limit: Maximum number of articles to return. Default is 10.
    
    Returns:
        List of Article objects sorted by publish date (newest first).
    
    Raises:
        ArticleFetchError: If the external API returns an error.
        RateLimitError: If too many requests are made in a short period.
    """
    # ... implementation
```

### ❌ BAD - Missing or minimal docstring

```python
def fetch_articles(sport, limit=10):
    """Fetch articles."""
    # ... implementation
```

### ❌ BAD - Docstring without useful information

```python
def process_data(data):
    """Process the data.
    
    This function processes data.
    
    Args:
        data: The data to process.
    
    Returns:
        Processed data.
    """
    # ... implementation
```

---

## Classes

### ✅ GOOD - Complete class with docstring and type hints

```python
class ArticleFetcher:
    """Fetches articles from external sources with caching and rate limiting.
    
    This class provides a unified interface for fetching sports articles
    from multiple data sources. It handles caching to reduce API calls
    and implements exponential backoff for rate limit errors.
    
    Attributes:
        cache: In-memory cache for fetched articles.
        rate_limiter: Token bucket rate limiter.
        max_retries: Maximum number of retry attempts for failed requests.
    """
    
    def __init__(self, cache_ttl: int = 3600, max_retries: int = 3) -> None:
        """Initialize the ArticleFetcher.
        
        Args:
            cache_ttl: Time-to-live for cached articles in seconds.
            max_retries: Maximum retry attempts for failed API calls.
        """
        self.cache_ttl = cache_ttl
        self.max_retries = max_retries
        self._cache: dict[str, tuple[Article, float]] = {}
    
    def fetch(self, sport: str, limit: int = 10) -> list[Article]:
        """Fetch articles for a given sport.
        
        Args:
            sport: The sport category to fetch.
            limit: Maximum number of articles to return.
        
        Returns:
            List of Article objects.
        """
        # ... implementation
```

### ❌ BAD - Class without docstring

```python
class ArticleFetcher:
    def __init__(self, cache_ttl=3600, max_retries=3):
        self.cache_ttl = cache_ttl
        self.max_retries = max_retries
        self._cache = {}
```

---

## Constants and Magic Numbers

### ✅ GOOD - Named constants with explanation

```python
# At module level
MAX_ARTICLE_LENGTH = 10_000  # Maximum characters per article
DEFAULT_LIMIT = 10  # Default number of articles to fetch
CACHE_TTL_SECONDS = 3600  # One hour cache TTL
RETRY_BACKOFF_BASE = 2  # Exponential backoff base in seconds

def process_article(content: str) -> str:
    """Process article content with length validation."""
    if len(content) > MAX_ARTICLE_LENGTH:
        raise ValueError(f"Article exceeds maximum length of {MAX_ARTICLE_LENGTH}")
    return content.strip()
```

### ❌ BAD - Magic numbers scattered throughout

```python
def process_article(content: str) -> str:
    if len(content) > 10000:
        raise ValueError("Article too long")
    return content.strip()
```

---

## Error Handling

### ✅ GOOD - Specific exceptions with context

```python
class ArticleFetchError(Exception):
    """Raised when article fetching fails."""
    
    def __init__(self, sport: str, reason: str) -> None:
        self.sport = sport
        self.reason = reason
        super().__init__(f"Failed to fetch {sport} articles: {reason}")


def fetch_articles(sport: str) -> list[Article]:
    """Fetch articles for a given sport."""
    try:
        response = _make_request(sport)
    except RateLimitError as e:
        raise ArticleFetchError(sport, "Rate limit exceeded") from e
    except APIError as e:
        raise ArticleFetchError(sport, str(e)) from e
    
    return _parse_response(response)
```

### ❌ BAD - Generic exception catching

```python
def fetch_articles(sport):
    try:
        response = _make_request(sport)
    except Exception:
        return []
```

---

## Imports

### ✅ GOOD - Organized, explicit imports

```python
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from agent.claude_client import ClaudeClient
from agent.context_window import ContextWindow
from tools.base_tool import BaseTool
from utils.logger.logger import setup_logger


# ... rest of code
```

### ❌ BAD - Wildcard imports

```python
from agent import *  # What is actually used?
from utils import *  # Namespace pollution
```

---

## Complex Functions - Step by Step

### ✅ GOOD - Clear step-by-step logic

```python
def process_workflow(task: Task) -> WorkflowResult:
    """Process a complete workflow task.
    
    Breaks down the task into discrete steps:
    1. Validate input
    2. Fetch required data
    3. Process data
    4. Format output
    
    Args:
        task: The task to process.
    
    Returns:
        WorkflowResult with processed output.
    
    Raises:
        ValidationError: If task input is invalid.
        ProcessingError: If processing fails.
    """
    # Step 1: Validate input
    _validate_task(task)
    
    # Step 2: Fetch required data
    articles = _fetch_articles(task.sport)
    
    # Step 3: Process data
    processed = _process_articles(articles, task.filters)
    
    # Step 4: Format output
    return WorkflowResult(
        articles=processed,
        metadata=_build_metadata(task),
    )
```

### ❌ BAD - Everything in one nested block

```python
def process_workflow(task):
    if task:
        articles = _fetch_articles(task.sport) if task.sport else None
        if articles:
            processed = [_process(a, task.filters) for a in articles]
            return WorkflowResult(articles=processed)
    return WorkflowResult(articles=[])
```

---

## Testing Considerations

### ✅ GOOD - Testable code with dependency injection

```python
class ArticleProcessor:
    """Processes articles with configurable transformers."""
    
    def __init__(
        self,
        transformer: ArticleTransformer | None = None,
        validator: ArticleValidator | None = None,
    ) -> None:
        """Initialize with optional dependencies.
        
        Args:
            transformer: Custom article transformer. Defaults to DefaultTransformer.
            validator: Custom article validator. Defaults to DefaultValidator.
        """
        self.transformer = transformer or DefaultTransformer()
        self.validator = validator or DefaultValidator()
    
    def process(self, article: dict[str, Any]) -> Article:
        """Process a raw article dictionary."""
        validated = self.validator.validate(article)
        return self.transformer.transform(validated)
```

### ❌ BAD - Hard-coded dependencies (hard to test)

```python
class ArticleProcessor:
    def process(self, article):
        # Always uses real services, can't mock for tests
        validator = RealArticleValidator()
        transformer = RealArticleTransformer()
        # ...
```

---

## Summary Checklist

Before marking code as complete, verify:

- [ ] All functions have type hints on parameters and return
- [ ] All public classes have docstrings
- [ ] All complex functions have docstrings with Args/Returns
- [ ] No magic numbers - use named constants
- [ ] Specific exceptions instead of generic catch-all
- [ ] No wildcard imports
- [ ] Code is broken into clear steps
- [ ] Dependencies can be injected (for testability)
- [ ] Passes `ruff check .`
- [ ] Passes `mypy .`