from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_detect_defaults(
    client: MCPToolCaller
) -> Any:
    """Apple Detect Defaults

    Detect sensible default mail, calendar, reminders, and notes targets, then persist them if missing.

    Example:
        await apple_detect_defaults(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_detect_defaults", payload)
