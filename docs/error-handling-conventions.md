# Error Handling Conventions

> **TL;DR**: Three patterns — LLM fallback chain, workflow checkpoint/resume, and tool output errors. Match the existing pattern for the layer you're working in.

## Pattern 1: LLM Fallback Chain (`agent/claude_client.py`)

LLM calls use a retry → fallback strategy:

```
Claude API call
  ├── RateLimitError → retry with backoff (up to max_retries)
  │     └── exhausted → fallback to Gemini
  ├── APIConnectionError → fallback to Gemini
  ├── AuthenticationError → fallback to Gemini
  ├── InternalServerError → fallback to Gemini
  └── success → return response
```

### When to use

Any code that calls `ClaudeClient.send_message()` or `ClaudeClient.send_message_with_tools()`. The fallback is handled internally — callers don't need to catch LLM errors.

### ✅ GOOD — Let the client handle fallback

```python
client = ClaudeClient(system_prompt=prompt)
response = client.send_message(user_message)  # fallback is automatic
```

### ❌ BAD — Wrapping LLM calls in try/except

```python
try:
    response = client.send_message(user_message)
except Exception:
    response = gemini_client.send_message(user_message)  # duplicates built-in fallback
```

### Gemini adapter

Gemini responses are normalized to Claude's format via `agent/gemini_adapter.py`. The adapter maps:
- Haiku → Flash, Sonnet → Pro (configured in `config/llms.yaml`)
- Tool schemas, messages, and responses are all adapted transparently

## Pattern 2: Workflow Checkpoint/Resume (`workflow/daily_workflow.py`)

The workflow uses checkpoint-based error recovery:

```python
try:
    return _execute_workflow(run_id, memory, steps_completed, cp_data, ...)
except Exception as e:
    logger.error(f'Workflow {run_id} failed: {e}')
    memory.update_workflow_run(run_id, {
        'status': 'failed',
        'error': str(e),
        'steps_completed': steps_completed,
    })
    send_failure_email(run_id=run_id, error=str(e), steps_completed=steps_completed)
    raise
finally:
    clear_log_context()
```

### Key behaviors

1. **Checkpoint after each step** — `steps_completed` list tracks progress, `cp_data` stores intermediate results
2. **Resume from checkpoint** — Pass `resume_run_id` to skip already-completed steps
3. **Failure email** — Sent on any unhandled exception with the run ID and error
4. **Re-raise** — The exception propagates to the scheduler so it can log the failure
5. **Log context cleanup** — `clear_log_context()` always runs in `finally`

### When to use

When adding a new workflow step:

```python
if 'new_step' not in completed:
    result = do_new_step()
    steps_completed.append('new_step')
    cp_data['new_step_result'] = result
    memory.save_checkpoint(run_id, steps_completed, cp_data)
```

### ❌ BAD — Swallowing errors in workflow steps

```python
try:
    result = do_new_step()
except Exception:
    result = None  # silently continues — breaks checkpoint integrity
```

## Pattern 3: Tool Output Errors (`tools/*.py`)

Tools report errors through their output objects, not exceptions. The agent loop handles tool errors gracefully.

### ✅ GOOD — Errors in output, not exceptions

```python
class FetchArticlesOutput(BaseModel):
    articles: list[dict] = []
    errors: list[str] = []
    source_counts: dict[str, int] = {}

# In the tool:
try:
    articles = collector.collect()
except Exception as e:
    output.errors.append(f'{source_name}: {e!s}')
    # continues to next source
```

### ✅ GOOD — Save API call result for dashboard tracking

```python
try:
    articles = collector.collect()
    memory.save_api_call_result(db_id, source_name, 'success', len(articles))
except Exception as e:
    output.errors.append(f'{source_name}: {e!s}')
    memory.save_api_call_result(db_id, source_name, 'error', error=str(e))
```

### ❌ BAD — Raising exceptions from tools

```python
def execute(self, input: FetchArticlesInput) -> FetchArticlesOutput:
    articles = collector.collect()  # unhandled exception kills the agent loop
    return FetchArticlesOutput(articles=articles)
```

## Pattern 4: Database Operations (`memory/memory.py`)

Database methods use try/finally for session cleanup:

```python
def get_recent_runs(self, limit: int = 30) -> list:
    session = get_session(self.engine)
    try:
        runs = session.query(WorkflowRun).order_by(...).limit(limit).all()
        return [...]
    finally:
        session.close()
```

For write operations, commit inside the try block. The `finally` ensures the session is always closed.

### ❌ BAD — Missing session cleanup

```python
def get_runs(self):
    session = get_session(self.engine)
    return session.query(WorkflowRun).all()  # session never closed
```

## Summary

| Layer | Pattern | Errors go to |
|-------|---------|-------------|
| LLM calls | Retry → Gemini fallback | Handled internally by ClaudeClient |
| Workflow | Checkpoint + failure email + re-raise | Scheduler, email, database |
| Tools | Output object `.errors` list | Agent loop (continues gracefully) |
| Database | try/finally session cleanup | Caller |
| Server routes | Flask error handlers + HTTP status codes | Client response |
