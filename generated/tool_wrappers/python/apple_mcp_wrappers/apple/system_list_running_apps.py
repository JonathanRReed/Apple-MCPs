from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def system_list_running_apps(
    client: MCPToolCaller
) -> Any:
    """System List Running Apps

    Delegated Apple domain tool 'system_list_running_apps' exposed through Apple-Tools-MCP.

    Example:
        await system_list_running_apps(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "system_list_running_apps", payload)
