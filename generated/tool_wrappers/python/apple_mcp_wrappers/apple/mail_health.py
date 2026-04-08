from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def mail_health(
    client: MCPToolCaller
) -> Any:
    """Mail Health

    Delegated Apple domain tool 'mail_health' exposed through Apple-Tools-MCP.

    Example:
        await mail_health(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "mail_health", payload)
