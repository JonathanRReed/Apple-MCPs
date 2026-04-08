from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_tag_file(
    client: MCPToolCaller,
    path: str,
    action: str | None = None,
    tags: list[Any] | None = None
) -> Any:
    """Apple Tag File

    Read, replace, add, or remove Finder tags on a file or folder through Apple Files.

    Example:
        await apple_tag_file(client, path='/path/to/item', action='example_action')
    """
    arguments = {
        "path": path,
        "action": action,
        "tags": tags,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_tag_file", payload)
