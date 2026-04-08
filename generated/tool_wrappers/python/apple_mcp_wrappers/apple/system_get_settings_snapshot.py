from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def system_get_settings_snapshot(
    client: MCPToolCaller
) -> Any:
    """System Get Settings Snapshot

    Delegated Apple domain tool 'system_get_settings_snapshot' exposed through Apple-Tools-MCP.

    Example:
        await system_get_settings_snapshot(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "system_get_settings_snapshot", payload)
