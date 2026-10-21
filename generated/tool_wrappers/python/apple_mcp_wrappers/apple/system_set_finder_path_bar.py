from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def system_set_finder_path_bar(
    client: MCPToolCaller,
    enabled: bool
) -> Any:
    """Set Finder Path Bar

    Show or hide the Finder path bar.

    Example:
        await system_set_finder_path_bar(client, enabled=False)
    """
    arguments = {
        "enabled": enabled,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "system_set_finder_path_bar", payload)
