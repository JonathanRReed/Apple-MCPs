from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def notes_move_note(
    client: MCPToolCaller,
    note_id: str,
    folder_id: str
) -> Any:
    """Notes Move Note

    Delegated Apple domain tool 'notes_move_note' exposed through Apple-Tools-MCP.

    Example:
        await notes_move_note(client, note_id='example_note_id', folder_id='example_folder_id')
    """
    arguments = {
        "note_id": note_id,
        "folder_id": folder_id,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "notes_move_note", payload)
