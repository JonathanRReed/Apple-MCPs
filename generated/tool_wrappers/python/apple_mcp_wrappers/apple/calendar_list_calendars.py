from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def calendar_list_calendars(
    client: MCPToolCaller
) -> Any:
    """Calendar List Calendars

    List available Apple Calendar calendars. Select by name and source, then pass the returned calendar_id unchanged. Re-list after Calendar access changes to refresh identifiers.

    Example:
        await calendar_list_calendars(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "calendar_list_calendars", payload)
