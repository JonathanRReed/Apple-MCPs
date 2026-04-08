from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def system_get_appearance_settings(
    client: MCPToolCaller
) -> Any:
    """Get Appearance Settings

    Read current macOS appearance settings such as light or dark mode and accent color.

    Example:
        await system_get_appearance_settings(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "system_get_appearance_settings", payload)
