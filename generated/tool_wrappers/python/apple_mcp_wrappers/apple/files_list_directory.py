from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def files_list_directory(
    client: MCPToolCaller,
    path: str
) -> Any:
    """Files List Directory

    Delegated Apple domain tool 'files_list_directory' exposed through Apple-Tools-MCP.

    Example:
        await files_list_directory(client, path='/path/to/item')
    """
    arguments = {
        "path": path,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "files_list_directory", payload)
