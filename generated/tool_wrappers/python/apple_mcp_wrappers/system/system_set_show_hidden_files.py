from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def system_set_show_hidden_files(
    client: MCPToolCaller,
    enabled: bool
) -> Any:
    """Set Show Hidden Files

    Show or hide hidden files in Finder.

    Example:
        await system_set_show_hidden_files(client, enabled=False)
    """
    arguments = {
        "enabled": enabled,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "system_set_show_hidden_files", payload)
