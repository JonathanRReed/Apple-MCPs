from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_get_system_context(
    client: MCPToolCaller
) -> Any:
    """Apple Get System Context

    Return a richer Apple system context snapshot, including Focus, frontmost app, and battery state.

    Example:
        await apple_get_system_context(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_get_system_context", payload)
