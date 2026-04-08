from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_maps_search_places_strict(
    client: MCPToolCaller,
    query: str,
    limit: int | None = None
) -> Any:
    """Apple Maps Search Places Strict

    Search places through the native Apple Maps MCP and fail closed if the Maps helper is unavailable.

    Example:
        await apple_maps_search_places_strict(client, query='find apple', limit=1)
    """
    arguments = {
        "query": query,
        "limit": limit,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_maps_search_places_strict", payload)
