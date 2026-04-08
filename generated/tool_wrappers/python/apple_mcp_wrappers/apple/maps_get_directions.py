from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def maps_get_directions(
    client: MCPToolCaller,
    origin: str,
    destination: str,
    transport: str | None = None
) -> Any:
    """Maps Get Directions

    Delegated Apple domain tool 'maps_get_directions' exposed through Apple-Tools-MCP.

    Example:
        await maps_get_directions(client, origin='example_origin', destination='example_destination')
    """
    arguments = {
        "origin": origin,
        "destination": destination,
        "transport": transport,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "maps_get_directions", payload)
