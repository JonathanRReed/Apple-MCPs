from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_create_event_interactive(
    client: MCPToolCaller,
    title: str | None = None,
    start_iso: str | None = None,
    end_iso: str | None = None,
    calendar_id: str | None = None,
    notes: str | None = None,
    location: str | None = None,
    all_day: bool | None = None
) -> Any:
    """Apple Create Event Interactive

    Create a Calendar event, asking for missing event details when needed.

    Example:
        await apple_create_event_interactive(client, title='example_title', start_iso='2026-04-07T18:00:00')
    """
    arguments = {
        "title": title,
        "start_iso": start_iso,
        "end_iso": end_iso,
        "calendar_id": calendar_id,
        "notes": notes,
        "location": location,
        "all_day": all_day,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_create_event_interactive", payload)
