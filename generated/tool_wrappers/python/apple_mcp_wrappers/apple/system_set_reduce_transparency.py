from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def system_set_reduce_transparency(
    client: MCPToolCaller,
    enabled: bool
) -> Any:
    """System Set Reduce Transparency

    Delegated Apple domain tool 'system_set_reduce_transparency' exposed through Apple-Tools-MCP.

    Example:
        await system_set_reduce_transparency(client, enabled=False)
    """
    arguments = {
        "enabled": enabled,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "system_set_reduce_transparency", payload)
