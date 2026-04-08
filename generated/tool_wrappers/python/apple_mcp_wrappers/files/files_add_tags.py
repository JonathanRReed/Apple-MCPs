from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def files_add_tags(
    client: MCPToolCaller,
    path: str,
    tags: list[Any]
) -> Any:
    """Add Tags

    Add Finder tags to a file or folder. Requires safe_manage or full_access safety mode.

    Example:
        await files_add_tags(client, path='/path/to/item', tags=[])
    """
    arguments = {
        "path": path,
        "tags": tags,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "files_add_tags", payload)
