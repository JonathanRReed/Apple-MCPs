from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def notes_append_to_note(
    client: MCPToolCaller,
    note_id: str,
    body_text: str | None = None,
    body_html: str | None = None
) -> Any:
    """Append to Note

    Append text to an existing note without replacing its current content. Provide body_text for plain text or body_html for rich content.

    Example:
        await notes_append_to_note(client, note_id='example_note_id', body_text='example_body_text')
    """
    arguments = {
        "note_id": note_id,
        "body_text": body_text,
        "body_html": body_html,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "notes_append_to_note", payload)
