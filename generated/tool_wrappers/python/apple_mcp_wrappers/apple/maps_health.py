from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def maps_health(
    client: MCPToolCaller
) -> Any:
    """Maps Health

    Delegated Apple domain tool 'maps_health' exposed through Apple-Tools-MCP.

    Example:
        await maps_health(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "maps_health", payload)
