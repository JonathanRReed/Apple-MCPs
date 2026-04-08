from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def calendar_recheck_permissions(
    client: MCPToolCaller
) -> Any:
    """Calendar Recheck Permissions

    Recheck Calendar access after the user changes macOS permissions, and notify the client that Calendar resources changed.

    Example:
        await calendar_recheck_permissions(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "calendar_recheck_permissions", payload)
