from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def notes_delete_folder(
    client: MCPToolCaller,
    folder_id: str
) -> Any:
    """Delete Folder

    Delete an Apple Notes folder.

    Example:
        await notes_delete_folder(client, folder_id='example_folder_id')
    """
    arguments = {
        "folder_id": folder_id,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "notes_delete_folder", payload)
