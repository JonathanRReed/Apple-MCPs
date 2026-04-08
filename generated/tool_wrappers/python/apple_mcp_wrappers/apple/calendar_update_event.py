from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def calendar_update_event(
    client: MCPToolCaller,
    event_id: str,
    title: str | None = None,
    start_iso: str | None = None,
    end_iso: str | None = None,
    calendar_id: str | None = None,
    notes: str | None = None,
    location: str | None = None,
    all_day: bool | None = None,
    recurrence: dict[str, Any] | None = None
) -> Any:
    """Calendar Update Event

    Delegated Apple domain tool 'calendar_update_event' exposed through Apple-Tools-MCP.

    Example:
        await calendar_update_event(client, event_id='example_event_id', title='example_title')
    """
    arguments = {
        "event_id": event_id,
        "title": title,
        "start_iso": start_iso,
        "end_iso": end_iso,
        "calendar_id": calendar_id,
        "notes": notes,
        "location": location,
        "all_day": all_day,
        "recurrence": recurrence,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "calendar_update_event", payload)
