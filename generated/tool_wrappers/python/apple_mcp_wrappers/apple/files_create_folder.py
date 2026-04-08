from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def files_create_folder(
    client: MCPToolCaller,
    path: str
) -> Any:
    """Files Create Folder

    Delegated Apple domain tool 'files_create_folder' exposed through Apple-Tools-MCP.

    Example:
        await files_create_folder(client, path='/path/to/item')
    """
    arguments = {
        "path": path,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "files_create_folder", payload)
