from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def files_reveal_in_finder(
    client: MCPToolCaller,
    path: str
) -> Any:
    """Files Reveal In Finder

    Delegated Apple domain tool 'files_reveal_in_finder' exposed through Apple-Tools-MCP.

    Example:
        await files_reveal_in_finder(client, path='/path/to/item')
    """
    arguments = {
        "path": path,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "files_reveal_in_finder", payload)
