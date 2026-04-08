from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def calendar_permission_guide(
    client: MCPToolCaller
) -> Any:
    """Calendar Permission Guide

    Explain how to grant Apple Calendar permission on macOS.

    Example:
        await calendar_permission_guide(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "calendar_permission_guide", payload)
