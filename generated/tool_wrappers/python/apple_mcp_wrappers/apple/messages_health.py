from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def messages_health(
    client: MCPToolCaller
) -> Any:
    """Messages Health

    Delegated Apple domain tool 'messages_health' exposed through Apple-Tools-MCP.

    Example:
        await messages_health(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "messages_health", payload)
