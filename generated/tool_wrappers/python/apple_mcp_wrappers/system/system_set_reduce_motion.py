from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def system_set_reduce_motion(
    client: MCPToolCaller,
    enabled: bool
) -> Any:
    """Set Reduce Motion

    Enable or disable macOS reduce motion accessibility mode.

    Example:
        await system_set_reduce_motion(client, enabled=False)
    """
    arguments = {
        "enabled": enabled,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "system_set_reduce_motion", payload)
