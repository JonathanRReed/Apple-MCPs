from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def system_set_dock_autohide(
    client: MCPToolCaller,
    enabled: bool
) -> Any:
    """System Set Dock Autohide

    Delegated Apple domain tool 'system_set_dock_autohide' exposed through Apple-Tools-MCP.

    Example:
        await system_set_dock_autohide(client, enabled=False)
    """
    arguments = {
        "enabled": enabled,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "system_set_dock_autohide", payload)
