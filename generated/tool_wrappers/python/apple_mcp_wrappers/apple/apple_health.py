from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_health(
    client: MCPToolCaller
) -> Any:
    """Apple Health

    Report aggregated health across the unified Apple ecosystem MCP domains.

    Example:
        await apple_health(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_health", payload)
