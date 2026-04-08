from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def files_list_recent_locations(
    client: MCPToolCaller,
    limit: int | None = None
) -> Any:
    """List Recent Locations

    List recently active parent folders across the allowed roots, including iCloud-aware metadata.

    Example:
        await files_list_recent_locations(client, limit=1)
    """
    arguments = {
        "limit": limit,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "files_list_recent_locations", payload)
