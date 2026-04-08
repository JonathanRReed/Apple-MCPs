from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def files_remove_tags(
    client: MCPToolCaller,
    path: str,
    tags: list[Any]
) -> Any:
    """Remove Tags

    Remove Finder tags from a file or folder. Requires safe_manage or full_access safety mode.

    Example:
        await files_remove_tags(client, path='/path/to/item', tags=[])
    """
    arguments = {
        "path": path,
        "tags": tags,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "files_remove_tags", payload)
