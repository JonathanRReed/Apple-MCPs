from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_reveal_in_finder(
    client: MCPToolCaller,
    path: str
) -> Any:
    """Apple Reveal In Finder

    Reveal a file or folder in Finder through Apple Files.

    Example:
        await apple_reveal_in_finder(client, path='/path/to/item')
    """
    arguments = {
        "path": path,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_reveal_in_finder", payload)
