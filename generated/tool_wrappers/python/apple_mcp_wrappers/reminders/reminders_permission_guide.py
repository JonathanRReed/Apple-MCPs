from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def reminders_permission_guide(
    client: MCPToolCaller
) -> Any:
    """Reminders Permission Guide

    Explain how to grant Apple Reminders permission on macOS.

    Example:
        await reminders_permission_guide(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "reminders_permission_guide", payload)
