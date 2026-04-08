from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def files_set_tags(
    client: MCPToolCaller,
    path: str,
    tags: list[Any]
) -> Any:
    """Files Set Tags

    Delegated Apple domain tool 'files_set_tags' exposed through Apple-Tools-MCP.

    Example:
        await files_set_tags(client, path='/path/to/item', tags=[])
    """
    arguments = {
        "path": path,
        "tags": tags,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "files_set_tags", payload)
