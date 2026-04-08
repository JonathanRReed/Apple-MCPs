from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def notes_list_attachments(
    client: MCPToolCaller,
    note_id: str
) -> Any:
    """List Attachments

    List attachments for a note.

    Example:
        await notes_list_attachments(client, note_id='example_note_id')
    """
    arguments = {
        "note_id": note_id,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "notes_list_attachments", payload)
