from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def files_open_path(
    client: MCPToolCaller,
    path: str
) -> Any:
    """Open Path

    Open a file or folder in the default app. Requires safe_manage or full_access safety mode.

    Example:
        await files_open_path(client, path='/path/to/item')
    """
    arguments = {
        "path": path,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "files_open_path", payload)
