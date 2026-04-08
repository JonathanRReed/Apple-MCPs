from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def calendar_create_event(
    client: MCPToolCaller,
    title: str,
    start_iso: str,
    end_iso: str,
    calendar_id: str,
    notes: str | None = None,
    location: str | None = None,
    all_day: bool | None = None,
    recurrence: dict[str, Any] | None = None
) -> Any:
    """Create Event

    Create a new event in a specific Apple Calendar calendar.

    Example:
        await calendar_create_event(client, title='example_title', start_iso='2026-04-07T18:00:00', end_iso='2026-04-07T18:00:00', calendar_id='example_calendar_id')
    """
    arguments = {
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
    return await call_tool_json(client, "calendar_create_event", payload)
