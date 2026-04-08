from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def system_set_appearance_mode(
    client: MCPToolCaller,
    mode: str
) -> Any:
    """System Set Appearance Mode

    Delegated Apple domain tool 'system_set_appearance_mode' exposed through Apple-Tools-MCP.

    Example:
        await system_set_appearance_mode(client, mode='example_mode')
    """
    arguments = {
        "mode": mode,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "system_set_appearance_mode", payload)
