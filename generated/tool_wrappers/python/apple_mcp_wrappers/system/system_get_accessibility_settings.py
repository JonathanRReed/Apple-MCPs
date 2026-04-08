from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def system_get_accessibility_settings(
    client: MCPToolCaller
) -> Any:
    """Get Accessibility Settings

    Read common macOS accessibility settings such as reduce motion and increase contrast.

    Example:
        await system_get_accessibility_settings(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "system_get_accessibility_settings", payload)
