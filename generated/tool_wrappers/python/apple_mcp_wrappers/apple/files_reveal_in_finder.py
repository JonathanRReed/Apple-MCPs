from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def files_reveal_in_finder(
    client: MCPToolCaller,
    path: str
) -> Any:
    """Reveal In Finder

    Reveal a file or folder in Finder. Requires safe_manage or full_access safety mode.

    Example:
        await files_reveal_in_finder(client, path='/path/to/item')
    """
    arguments = {
        "path": path,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "files_reveal_in_finder", payload)
