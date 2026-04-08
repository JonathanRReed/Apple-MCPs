from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def system_get_dock_settings(
    client: MCPToolCaller
) -> Any:
    """Get Dock Settings

    Read common macOS Dock settings such as autohide, magnification, and orientation.

    Example:
        await system_get_dock_settings(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "system_get_dock_settings", payload)
