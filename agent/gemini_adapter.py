"""Adapter to normalize Gemini responses to Claude's Message/ContentBlock format."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TextBlock:
    """Mimics anthropic TextBlock."""

    text: str
    type: str = 'text'


@dataclass
class ToolUseBlock:
    """Mimics anthropic ToolUseBlock."""

    name: str
    input: dict[str, Any]
    id: str = ''
    type: str = 'tool_use'


@dataclass
class AdaptedMessage:
    """Mimics anthropic Message with content blocks."""

    content: list[TextBlock | ToolUseBlock] = field(default_factory=list)
    stop_reason: str | None = None


def adapt_tools(claude_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert Claude tool definitions to Gemini FunctionDeclaration format.

    Args:
        claude_tools: List of Claude tool dicts with name, description, input_schema.

    Returns:
        List of Gemini-compatible function declaration dicts.
    """
    declarations = []
    for tool in claude_tools:
        schema = dict(tool.get('input_schema', {}))
        # Gemini doesn't use the top-level 'type' the same way
        params = {
            'type': schema.get('type', 'object'),
            'properties': schema.get('properties', {}),
        }
        if 'required' in schema:
            params['required'] = schema['required']

        declarations.append(
            {
                'name': tool['name'],
                'description': tool.get('description', ''),
                'parameters': params,
            }
        )
    return declarations


def adapt_response(gemini_response: Any) -> AdaptedMessage:
    """Convert a Gemini response to Claude's Message format.

    Args:
        gemini_response: Response from google.genai GenerateContent.

    Returns:
        AdaptedMessage with TextBlock and/or ToolUseBlock content.
    """
    blocks: list[TextBlock | ToolUseBlock] = []

    if not gemini_response or not gemini_response.candidates:
        return AdaptedMessage(content=[TextBlock(text='')])

    candidate = gemini_response.candidates[0]
    parts = getattr(candidate.content, 'parts', []) if candidate.content else []

    tool_use_counter = 0
    for part in parts:
        if hasattr(part, 'function_call') and part.function_call:
            fc = part.function_call
            args = dict(fc.args) if fc.args else {}
            blocks.append(
                ToolUseBlock(
                    name=fc.name,
                    input=args,
                    id=f'gemini-{tool_use_counter}',
                )
            )
            tool_use_counter += 1
        elif hasattr(part, 'text') and part.text:
            blocks.append(TextBlock(text=part.text))

    if not blocks:
        text = getattr(gemini_response, 'text', '') or ''
        blocks.append(TextBlock(text=text))

    return AdaptedMessage(content=blocks)


def adapt_messages(
    claude_messages: list[dict[str, Any]], system_prompt: str
) -> tuple[str, list[dict[str, Any]]]:
    """Convert Claude message format to Gemini content format.

    Args:
        claude_messages: Claude-format messages with role and content.
        system_prompt: System prompt (becomes Gemini system_instruction).

    Returns:
        Tuple of (system_instruction, gemini_contents).
    """
    contents: list[dict[str, Any]] = []

    for msg in claude_messages:
        role = msg.get('role', 'user')
        content = msg.get('content', '')

        # Map Claude roles to Gemini roles
        gemini_role = 'model' if role == 'assistant' else 'user'

        if isinstance(content, str):
            contents.append({'role': gemini_role, 'parts': [{'text': content}]})
        elif isinstance(content, list):
            parts: list[dict[str, Any]] = []
            for item in content:
                if isinstance(item, dict):
                    if item.get('type') == 'tool_use':
                        parts.append(
                            {
                                'function_call': {
                                    'name': item.get('name', ''),
                                    'args': item.get('input', {}),
                                }
                            }
                        )
                    elif item.get('type') == 'tool_result':
                        parts.append(
                            {
                                'function_response': {
                                    'name': 'tool_result',
                                    'response': {'content': item.get('content', '')},
                                }
                            }
                        )
                    elif item.get('type') == 'text':
                        parts.append({'text': item.get('text', '')})
                    else:
                        parts.append({'text': str(item)})
                else:
                    parts.append({'text': str(item)})
            if parts:
                contents.append({'role': gemini_role, 'parts': parts})

    return system_prompt, contents
