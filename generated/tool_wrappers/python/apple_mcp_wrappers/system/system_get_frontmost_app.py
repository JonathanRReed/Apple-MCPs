from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def system_get_frontmost_app(
    client: MCPToolCaller
) -> Any:
    """Get Frontmost App

    Get the name of the current frontmost application.

    Example:
        await system_get_frontmost_app(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "system_get_frontmost_app", payload)
