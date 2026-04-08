from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def files_get_file_info(
    client: MCPToolCaller,
    path: str
) -> Any:
    """Files Get File Info

    Delegated Apple domain tool 'files_get_file_info' exposed through Apple-Tools-MCP.

    Example:
        await files_get_file_info(client, path='/path/to/item')
    """
    arguments = {
        "path": path,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "files_get_file_info", payload)
