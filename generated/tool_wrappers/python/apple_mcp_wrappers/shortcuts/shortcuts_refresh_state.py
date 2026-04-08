from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def shortcuts_refresh_state(
    client: MCPToolCaller
) -> Any:
    """Shortcuts Refresh State

    Refresh Shortcuts resources and notify the client that the shortcut catalog may have changed.

    Example:
        await shortcuts_refresh_state(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "shortcuts_refresh_state", payload)
