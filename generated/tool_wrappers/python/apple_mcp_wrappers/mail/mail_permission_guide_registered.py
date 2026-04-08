from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def mail_permission_guide_registered(
    client: MCPToolCaller
) -> Any:
    """Mail Permission Guide

    Explain how to grant Apple Mail automation permission on macOS.

    Example:
        await mail_permission_guide_registered(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "mail_permission_guide_registered", payload)
