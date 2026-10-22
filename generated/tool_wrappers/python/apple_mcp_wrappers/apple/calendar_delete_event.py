from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def calendar_delete_event(
    client: MCPToolCaller,
    event_id: str
) -> Any:
    """Delete Event

    Delete a calendar event by event_id.

    Example:
        await calendar_delete_event(client, event_id='example_event_id')
    """
    arguments = {
        "event_id": event_id,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "calendar_delete_event", payload)
