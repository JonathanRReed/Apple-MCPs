from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def files_delete_path(
    client: MCPToolCaller,
    path: str
) -> Any:
    """Delete Path

    Delete a file or empty folder inside the allowed roots. Requires full_access safety mode.

    Example:
        await files_delete_path(client, path='/path/to/item')
    """
    arguments = {
        "path": path,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "files_delete_path", payload)
