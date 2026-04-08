from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def notes_append_to_note(
    client: MCPToolCaller,
    note_id: str,
    body: str
) -> Any:
    """Notes Append To Note

    Delegated Apple domain tool 'notes_append_to_note' exposed through Apple-Tools-MCP.

    Example:
        await notes_append_to_note(client, note_id='example_note_id', body='example_body')
    """
    arguments = {
        "note_id": note_id,
        "body": body,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "notes_append_to_note", payload)
