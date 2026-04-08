from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def health(
    client: MCPToolCaller
) -> Any:
    """Mail Health

    Report the active Apple Mail MCP configuration.

    Example:
        await health(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "health", payload)
