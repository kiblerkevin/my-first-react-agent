# Prompt Engineering Conventions

> **TL;DR**: Prompts live in `prompts/` as Python string constants. Use `.format()` placeholders. Keep system prompts separate from user messages.

## File Structure

```
prompts/
├── create_blog_draft_prompt.py      # Drafter system prompt
├── evaluate_blog_post_prompt.py     # Evaluator system prompt
├── revision_agent_prompt.py         # Orchestrator system prompt (has placeholders)
└── summarize_article_prompt.py      # Summarizer system prompt
```

Each file exports a single uppercase constant:

```python
# prompts/summarize_article_prompt.py
SUMMARIZE_ARTICLE_PROMPT = """
You are a sports news editor summarizing individual articles...
"""
```

## Prompt Types

### Static prompts (no placeholders)

Used by tools that always receive the same system instructions. The variable data comes in the user message.

```python
# ✅ GOOD — static system prompt, data in user message
SUMMARIZE_ARTICLE_PROMPT = """
You are a sports news editor summarizing individual articles...
Return only the JSON object. No explanation, no markdown, no code fences.
"""
```

### Dynamic prompts (with `.format()` placeholders)

Used when the system prompt needs runtime values (e.g., criterion floors, feedback).

```python
# ✅ GOOD — placeholders filled at runtime
REVISION_AGENT_PROMPT = """
You are a Chicago sports blog editor...

Criterion floors (minimum scores required):
{criterion_floors}

{rejection_feedback_section}
"""

# Filled in revision_agent.py:
system_prompt = REVISION_AGENT_PROMPT.format(
    criterion_floors=floors_str,
    rejection_feedback_section=feedback_section,
)
```

### ❌ BAD — f-strings or string concatenation

```python
# Don't do this — prompt is evaluated at import time
PROMPT = f"You are an editor. The threshold is {THRESHOLD}."

# Don't do this — hard to read and maintain
PROMPT = "You are an editor." + " The threshold is " + str(threshold) + "."
```

## Writing Guidelines

### Structure

1. **Role statement** — First line defines who the LLM is
2. **Input description** — What data the LLM will receive
3. **Output format** — Exact JSON schema or HTML structure expected
4. **Rules/constraints** — Mandatory behaviors, scoring rubrics, budget guards
5. **Strategy hints** — Prioritization guidance for edge cases

### ✅ GOOD — Explicit scoring rubric

```
- accuracy: Follow these steps exactly:
  1. For every completed game in the SCORES data, verify the score appears in the post
  2. Compare player names against the SUMMARIES data
  3. Score: 10 = all correct, 8 = minor errors, 5 = missing scores, 1 = fabricated
```

### ❌ BAD — Vague instructions

```
- accuracy: Check if the post is accurate. Score 1-10.
```

### ✅ GOOD — Explicit output format

```
Return a JSON object with exactly these fields:
{
  "summary": "2-3 sentence summary...",
  "event_type": "one of: game_recap, trade, injury, draft, roster, preview, opinion, other",
  "is_relevant": true or false
}
Return only the JSON object. No explanation, no markdown, no code fences.
```

### ❌ BAD — Ambiguous output expectations

```
Summarize the article and return the result.
```

## How Prompts Connect to Tools

| Prompt | Used By | LLM Role |
|--------|---------|----------|
| `SUMMARIZE_ARTICLE_PROMPT` | `SummarizeArticleTool` | Haiku (summarizer) |
| `CREATE_BLOG_DRAFT_PROMPT` | `CreateBlogDraftTool` | Sonnet (drafter) |
| `EVALUATE_BLOG_POST_PROMPT` | `EvaluateBlogPostTool` | Sonnet (evaluator) |
| `REVISION_AGENT_PROMPT` | `RevisionAgent` | Haiku (orchestrator) |

LLM model assignments are in `config/llms.yaml`. The prompt is the system message; the tool builds the user message with the actual data.

## Modifying Prompts

1. **Read the existing prompt** fully before making changes
2. **Check the tool** that uses it — understand what data is injected as the user message
3. **Check the evaluation criteria** — if modifying the draft prompt, the evaluator prompt must stay aligned
4. **Test with a real run** — prompt changes can have subtle effects on output quality
5. **Don't break the format contract** — if the tool parses JSON output, the prompt must still request that exact format

## Revision Agent Placeholders

The `REVISION_AGENT_PROMPT` has two placeholders:

| Placeholder | Source | Example Value |
|-------------|--------|---------------|
| `{criterion_floors}` | `config/orchestration.yaml` → `revision_loop.criterion_floors` | `accuracy: 7/10\ncompleteness: 7/10` |
| `{rejection_feedback_section}` | Human rejection feedback (or empty string) | `Previous rejection feedback: Add more detail about the Cubs game` |
