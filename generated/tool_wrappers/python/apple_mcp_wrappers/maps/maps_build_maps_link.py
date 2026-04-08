from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def maps_build_maps_link(
    client: MCPToolCaller,
    destination: str,
    origin: str | None = None,
    transport: str | None = None
) -> Any:
    """Build Maps Link

    Build an Apple Maps URL for a destination or route.

    Example:
        await maps_build_maps_link(client, destination='example_destination', origin='example_origin')
    """
    arguments = {
        "destination": destination,
        "origin": origin,
        "transport": transport,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "maps_build_maps_link", payload)
