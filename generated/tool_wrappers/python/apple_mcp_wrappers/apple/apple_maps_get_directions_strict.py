from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_maps_get_directions_strict(
    client: MCPToolCaller,
    origin: str,
    destination: str,
    transport: str | None = None
) -> Any:
    """Apple Maps Get Directions Strict

    Get directions through the native Apple Maps MCP and fail closed if the Maps helper is unavailable.

    Example:
        await apple_maps_get_directions_strict(client, origin='example_origin', destination='example_destination')
    """
    arguments = {
        "origin": origin,
        "destination": destination,
        "transport": transport,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_maps_get_directions_strict", payload)
