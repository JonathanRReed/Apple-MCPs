from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def notes_create_folder(
    client: MCPToolCaller,
    folder_name: str,
    account_name: str,
    parent_folder_id: str | None = None
) -> Any:
    """Notes Create Folder

    Delegated Apple domain tool 'notes_create_folder' exposed through Apple-Tools-MCP.

    Example:
        await notes_create_folder(client, folder_name='example_folder_name', account_name='example_account_name')
    """
    arguments = {
        "folder_name": folder_name,
        "account_name": account_name,
        "parent_folder_id": parent_folder_id,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "notes_create_folder", payload)
