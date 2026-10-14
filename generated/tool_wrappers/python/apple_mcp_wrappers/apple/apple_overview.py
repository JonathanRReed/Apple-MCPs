from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_overview(
    client: MCPToolCaller
) -> Any:
    """Apple Overview

    Return domain health and saved preferences; defer permission-sensitive data reads and Shortcuts library enumeration.

    Example:
        await apple_overview(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_overview", payload)
