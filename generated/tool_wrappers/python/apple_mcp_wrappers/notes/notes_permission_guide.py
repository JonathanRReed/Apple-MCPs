from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def notes_permission_guide(
    client: MCPToolCaller
) -> Any:
    """Notes Permission Guide

    Explain how to grant Apple Notes automation permission on macOS.

    Example:
        await notes_permission_guide(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "notes_permission_guide", payload)
