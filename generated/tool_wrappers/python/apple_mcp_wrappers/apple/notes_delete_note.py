from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def notes_delete_note(
    client: MCPToolCaller,
    note_id: str
) -> Any:
    """Delete Note

    Delete a note by note_id.

    Example:
        await notes_delete_note(client, note_id='example_note_id')
    """
    arguments = {
        "note_id": note_id,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "notes_delete_note", payload)
