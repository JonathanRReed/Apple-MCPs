from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def notes_rename_folder(
    client: MCPToolCaller,
    folder_id: str,
    folder_name: str
) -> Any:
    """Notes Rename Folder

    Delegated Apple domain tool 'notes_rename_folder' exposed through Apple-Tools-MCP.

    Example:
        await notes_rename_folder(client, folder_id='example_folder_id', folder_name='example_folder_name')
    """
    arguments = {
        "folder_id": folder_id,
        "folder_name": folder_name,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "notes_rename_folder", payload)
