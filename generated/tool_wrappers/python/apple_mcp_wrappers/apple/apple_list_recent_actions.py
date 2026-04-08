from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_list_recent_actions(
    client: MCPToolCaller,
    limit: int | None = None
) -> Any:
    """Apple List Recent Actions

    List recent assistant actions recorded by Apple-Tools for audit and undo workflows.

    Example:
        await apple_list_recent_actions(client, limit=1)
    """
    arguments = {
        "limit": limit,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_list_recent_actions", payload)
