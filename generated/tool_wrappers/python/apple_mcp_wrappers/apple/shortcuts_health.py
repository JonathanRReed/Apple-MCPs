from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def shortcuts_health(
    client: MCPToolCaller
) -> Any:
    """Shortcuts Health

    Delegated Apple domain tool 'shortcuts_health' exposed through Apple-Tools-MCP.

    Example:
        await shortcuts_health(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "shortcuts_health", payload)
