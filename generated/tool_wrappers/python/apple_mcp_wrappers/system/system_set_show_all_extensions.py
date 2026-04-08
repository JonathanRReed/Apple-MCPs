from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def system_set_show_all_extensions(
    client: MCPToolCaller,
    enabled: bool
) -> Any:
    """Set Show All Extensions

    Show or hide filename extensions in macOS.

    Example:
        await system_set_show_all_extensions(client, enabled=False)
    """
    arguments = {
        "enabled": enabled,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "system_set_show_all_extensions", payload)
