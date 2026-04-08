from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def system_set_appearance_mode(
    client: MCPToolCaller,
    mode: str
) -> Any:
    """Set Appearance Mode

    Set macOS appearance mode to light or dark.

    Example:
        await system_set_appearance_mode(client, mode='example_mode')
    """
    arguments = {
        "mode": mode,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "system_set_appearance_mode", payload)
