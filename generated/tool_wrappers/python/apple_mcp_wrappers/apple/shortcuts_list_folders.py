from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def shortcuts_list_folders(
    client: MCPToolCaller
) -> Any:
    """Shortcuts List Folders

    Delegated Apple domain tool 'shortcuts_list_folders' exposed through Apple-Tools-MCP.

    Example:
        await shortcuts_list_folders(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "shortcuts_list_folders", payload)
