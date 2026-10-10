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
    recurrence: dict[str, Any] | None = None,
    alarms: list[Any] | None = None
) -> Any:
    """Update Event

    Update one or more fields on an existing calendar event. For full alarm edits, list events using a native calendar_id and pass the returned native event_id. Existing applescript:: IDs continue to use automation after access changes. Optional alarms: list of {minutes_before: N} or {absolute_iso: ISO datetime}; pass [] to clear alarms, omit to leave unchanged. Replacing or clearing existing alarms, or combining explicit alarms with other field edits, requires native EventKit access. Automation rejects combined requests before any mutation, including [] or unchanged field values. Omit alarms for ordinary field edits; alarm-only initial alerts or [] no-ops require all alert collections verified empty.

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
        "alarms": alarms,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "calendar_update_event", payload)
