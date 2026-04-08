from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def contacts_permission_guide(
    client: MCPToolCaller
) -> Any:
    """Contacts Permission Guide

    Explain how to grant Apple Contacts permission on macOS.

    Example:
        await contacts_permission_guide(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "contacts_permission_guide", payload)
