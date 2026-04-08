from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def notes_update_note(
    client: MCPToolCaller,
    note_id: str,
    title: str | None = None,
    body_html: str | None = None,
    folder_id: str | None = None,
    tags: list[Any] | None = None
) -> Any:
    """Notes Update Note

    Delegated Apple domain tool 'notes_update_note' exposed through Apple-Tools-MCP.

    Example:
        await notes_update_note(client, note_id='example_note_id', title='example_title')
    """
    arguments = {
        "note_id": note_id,
        "title": title,
        "body_html": body_html,
        "folder_id": folder_id,
        "tags": tags,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "notes_update_note", payload)
