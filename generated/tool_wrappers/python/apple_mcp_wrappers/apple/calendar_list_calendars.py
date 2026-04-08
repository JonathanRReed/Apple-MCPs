from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def calendar_list_calendars(
    client: MCPToolCaller
) -> Any:
    """Calendar List Calendars

    Delegated Apple domain tool 'calendar_list_calendars' exposed through Apple-Tools-MCP.

    Example:
        await calendar_list_calendars(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "calendar_list_calendars", payload)
