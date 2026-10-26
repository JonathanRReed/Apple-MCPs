from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def calendar_delete_event(
    client: MCPToolCaller,
    event_id: str,
    scope: str | None = None,
    occurrence_start_iso: str | None = None
) -> Any:
    """Delete Event

    Delete a calendar event by event_id. For a repeating event (recurring: true in calendar_list_events), pass scope and, for one occurrence or those following it, occurrence_start_iso. Without scope, the user is asked to choose when the client supports forms; otherwise the call returns RECURRING_EVENT_SCOPE_REQUIRED and nothing changes.

    Example:
        await calendar_delete_event(client, event_id='example_event_id', scope='occurrence')
    """
    arguments = {
        "event_id": event_id,
        "scope": scope,
        "occurrence_start_iso": occurrence_start_iso,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "calendar_delete_event", payload)
