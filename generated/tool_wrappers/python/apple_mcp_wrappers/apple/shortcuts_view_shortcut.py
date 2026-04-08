from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def shortcuts_view_shortcut(
    client: MCPToolCaller,
    shortcut_name_or_identifier: str
) -> Any:
    """Shortcuts View Shortcut

    Delegated Apple domain tool 'shortcuts_view_shortcut' exposed through Apple-Tools-MCP.

    Example:
        await shortcuts_view_shortcut(client, shortcut_name_or_identifier='example_shortcut_name_or_identifier')
    """
    arguments = {
        "shortcut_name_or_identifier": shortcut_name_or_identifier,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "shortcuts_view_shortcut", payload)
