from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def files_open_path(
    client: MCPToolCaller,
    path: str
) -> Any:
    """Files Open Path

    Delegated Apple domain tool 'files_open_path' exposed through Apple-Tools-MCP.

    Example:
        await files_open_path(client, path='/path/to/item')
    """
    arguments = {
        "path": path,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "files_open_path", payload)
