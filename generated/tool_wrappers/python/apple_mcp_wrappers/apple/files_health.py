from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def files_health(
    client: MCPToolCaller
) -> Any:
    """Files Health

    Report the active Apple Files MCP configuration.

    Example:
        await files_health(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "files_health", payload)
