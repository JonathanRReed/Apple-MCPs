from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def maps_search_places(
    client: MCPToolCaller,
    query: str,
    limit: int | None = None
) -> Any:
    """Maps Search Places

    Delegated Apple domain tool 'maps_search_places' exposed through Apple-Tools-MCP.

    Example:
        await maps_search_places(client, query='find apple', limit=1)
    """
    arguments = {
        "query": query,
        "limit": limit,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "maps_search_places", payload)
