from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def calendar_get_event(
    client: MCPToolCaller,
    event_id: str
) -> Any:
    """Calendar Get Event

    Read an Apple Calendar event, including relative, absolute, and location-based alarms.

    Example:
        await calendar_get_event(client, event_id='example_event_id')
    """
    arguments = {
        "event_id": event_id,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "calendar_get_event", payload)
