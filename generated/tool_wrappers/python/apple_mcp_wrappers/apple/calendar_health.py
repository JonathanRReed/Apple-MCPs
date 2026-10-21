from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def calendar_health(
    client: MCPToolCaller
) -> Any:
    """Calendar Health

    Report the active Apple Calendar server configuration.

    Example:
        await calendar_health(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "calendar_health", payload)
