from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def shortcuts_list_shortcuts(
    client: MCPToolCaller,
    folder_name: str | None = None
) -> Any:
    """List Shortcuts

    List Apple Shortcuts, optionally restricted to one folder.

    Example:
        await shortcuts_list_shortcuts(client, folder_name='example_folder_name')
    """
    arguments = {
        "folder_name": folder_name,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "shortcuts_list_shortcuts", payload)
