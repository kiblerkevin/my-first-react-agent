# Architecture

> **TL;DR**: This is a multi-agent blog automation system that fetches sports articles, deduplicates them, generates summaries, evaluates quality, and publishes to WordPress.

## System Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Scheduler     │────▶│  Base Agent    │────▶│   Tools         │
│  (APScheduler)  │     │  (LLM Loop)    │     │  (Tool Use)     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                │                        │
                                ▼                        ▼
                        ┌─────────────────┐     ┌─────────────────┐
                        │  Context Window │     │   Outputs       │
                        │  (Message Hist) │     │  (WordPress)    │
                        └─────────────────┘     └─────────────────┘
```

## Why This Architecture?

### 1. Agent Pattern (BaseAgent)
- **Problem**: LLMs can't complete complex tasks in a single call
- **Solution**: Tool-use loop that iterates until text response
- **Trade-off**: More tokens, but handles multi-step reasoning

### 2. Tool Abstraction (BaseTool)
- **Problem**: Each tool had different interfaces
- **Solution**: Pydantic-based input/output schemas with consistent execute()
- **Trade-off**: More upfront code, but type safety and self-documenting

### 3. Context Window Management
- **Problem**: Long conversations exceed token limits
- **Solution**: Sliding window that preserves recent messages
- **Trade-off**: Lose some conversation history

### 4. Multi-Provider Support (Claude + Gemini)
- **Problem**: Vendor lock-in, cost variance
- **Solution**: Adapter pattern for LLM clients
- **Trade-off**: More abstraction, but flexibility

## Core Components

| Component | Purpose | Key File |
|-----------|---------|----------|
| **BaseAgent** | Tool-use loop orchestrator | `agent/base_agent.py` |
| **Tools** | Domain actions (fetch, summarize, publish) | `tools/*.py` |
| **Memory** | SQLite-backed conversation history | `memory/memory.py` |
| **Workflow** | Daily automation orchestration | `workflow/daily_workflow.py` |
| **Server** | Approval dashboard UI | `server/approval_server.py` |

## Data Flow

1. **Scheduler** triggers `DailyWorkflow.run()`
2. **Workflow** calls `BaseAgent` with task
3. **Agent** loops: LLM → Tool Call → Execute → Repeat
4. **Tools** fetch external data (articles, scores)
5. **Output** stored in memory, published to WordPress
6. **Approval** via dashboard before final publish

## Key Design Decisions

### Why SQLite for Memory?
- Simple, no external dependencies
- Sufficient for conversation history
- Easy backup (single file)

### Why Pydantic for Tools?
- Self-validating input/output
- IDE autocomplete
- Documentation from type hints

### Why Separate Claude/Gemini Clients?
- Swap providers without rewriting tools
- A/B test different models
- Handle provider-specific quirks

## Technology Stack

- **Python**: 3.12
- **LLM Clients**: Anthropic Claude, Google Gemini
- **Database**: SQLite (via SQLAlchemy)
- **Web**: Flask + vanilla HTML templates
- **Scheduling**: APScheduler
- **Linting**: Ruff
- **Type Checking**: mypy

## Future Considerations

- Add more LLM providers (OpenAI, local models)
- Replace SQLite with PostgreSQL for scale
- Add async tool execution
- Implement more sophisticated context eviction