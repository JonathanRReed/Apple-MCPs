from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def system_set_finder_path_bar(
    client: MCPToolCaller,
    enabled: bool
) -> Any:
    """System Set Finder Path Bar

    Delegated Apple domain tool 'system_set_finder_path_bar' exposed through Apple-Tools-MCP.

    Example:
        await system_set_finder_path_bar(client, enabled=False)
    """
    arguments = {
        "enabled": enabled,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "system_set_finder_path_bar", payload)
