from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def messages_permission_guide(
    client: MCPToolCaller
) -> Any:
    """Messages Permission Guide

    Explain how to grant Apple Messages permissions on macOS.

    Example:
        await messages_permission_guide(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "messages_permission_guide", payload)
