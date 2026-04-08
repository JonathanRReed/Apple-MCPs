from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_recheck_permissions(
    client: MCPToolCaller
) -> Any:
    """Apple Recheck Permissions

    Recheck Apple domain health after the user changes macOS permissions, and notify the client that Apple resources changed.

    Example:
        await apple_recheck_permissions(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_recheck_permissions", payload)
