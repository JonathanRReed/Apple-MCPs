from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_event_collaboration_summary(
    client: MCPToolCaller,
    event_id: str
) -> Any:
    """Apple Event Collaboration Summary

    Summarize attendee state for a shared calendar event so agents can verify collaboration and participation.

    Example:
        await apple_event_collaboration_summary(client, event_id='example_event_id')
    """
    arguments = {
        "event_id": event_id,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_event_collaboration_summary", payload)
