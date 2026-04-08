from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def system_status(
    client: MCPToolCaller
) -> Any:
    """System Status

    Delegated Apple domain tool 'system_status' exposed through Apple-Tools-MCP.

    Example:
        await system_status(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "system_status", payload)
