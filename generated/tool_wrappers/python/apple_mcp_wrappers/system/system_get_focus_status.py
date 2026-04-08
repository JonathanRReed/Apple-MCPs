from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def system_get_focus_status(
    client: MCPToolCaller
) -> Any:
    """Get Focus Status

    Return truthful Focus support metadata and the best available current Focus state.

    Example:
        await system_get_focus_status(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "system_get_focus_status", payload)
