from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def files_get_tags(
    client: MCPToolCaller,
    path: str
) -> Any:
    """Get Tags

    Read Finder tags for a file or folder inside the allowed roots.

    Example:
        await files_get_tags(client, path='/path/to/item')
    """
    arguments = {
        "path": path,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "files_get_tags", payload)
