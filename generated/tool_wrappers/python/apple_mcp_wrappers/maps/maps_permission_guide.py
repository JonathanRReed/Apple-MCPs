from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def maps_permission_guide(
    client: MCPToolCaller
) -> Any:
    """Maps Permission Guide

    Explain Apple Maps MCP local helper requirements on macOS.

    Example:
        await maps_permission_guide(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "maps_permission_guide", payload)
