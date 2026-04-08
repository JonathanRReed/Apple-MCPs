from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def shortcuts_permission_guide(
    client: MCPToolCaller
) -> Any:
    """Shortcuts Permission Guide

    Explain the runtime requirements for Apple Shortcuts on macOS.

    Example:
        await shortcuts_permission_guide(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "shortcuts_permission_guide", payload)
