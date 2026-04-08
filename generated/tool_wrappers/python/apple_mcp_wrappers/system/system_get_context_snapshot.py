from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def system_get_context_snapshot(
    client: MCPToolCaller
) -> Any:
    """Get System Context Snapshot

    Return a richer macOS context snapshot, including battery, frontmost app, and Focus metadata.

    Example:
        await system_get_context_snapshot(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "system_get_context_snapshot", payload)
