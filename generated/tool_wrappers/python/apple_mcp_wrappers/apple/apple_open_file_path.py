from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_open_file_path(
    client: MCPToolCaller,
    path: str
) -> Any:
    """Apple Open File Path

    Open a file or folder through Apple Files and return iCloud-aware path metadata.

    Example:
        await apple_open_file_path(client, path='/path/to/item')
    """
    arguments = {
        "path": path,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_open_file_path", payload)
