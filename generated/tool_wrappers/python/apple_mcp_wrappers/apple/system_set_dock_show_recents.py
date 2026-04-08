from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def system_set_dock_show_recents(
    client: MCPToolCaller,
    enabled: bool
) -> Any:
    """System Set Dock Show Recents

    Delegated Apple domain tool 'system_set_dock_show_recents' exposed through Apple-Tools-MCP.

    Example:
        await system_set_dock_show_recents(client, enabled=False)
    """
    arguments = {
        "enabled": enabled,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "system_set_dock_show_recents", payload)
