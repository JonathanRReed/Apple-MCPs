from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def system_get_battery(
    client: MCPToolCaller
) -> Any:
    """Get Battery

    Get the current battery state from macOS.

    Example:
        await system_get_battery(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "system_get_battery", payload)
