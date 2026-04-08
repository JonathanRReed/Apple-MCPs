from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_get_preferences(
    client: MCPToolCaller
) -> Any:
    """Apple Get Preferences

    Read the persisted Apple-Tools assistant defaults and routing preferences.

    Example:
        await apple_get_preferences(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_get_preferences", payload)
