from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def system_set_increase_contrast(
    client: MCPToolCaller,
    enabled: bool
) -> Any:
    """Set Increase Contrast

    Enable or disable macOS increase contrast accessibility mode.

    Example:
        await system_set_increase_contrast(client, enabled=False)
    """
    arguments = {
        "enabled": enabled,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "system_set_increase_contrast", payload)
