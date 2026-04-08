from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def calendar_list_events(
    client: MCPToolCaller,
    start_iso: str,
    end_iso: str,
    calendar_id: str | None = None,
    limit: int | None = None
) -> Any:
    """Calendar List Events

    Delegated Apple domain tool 'calendar_list_events' exposed through Apple-Tools-MCP.

    Example:
        await calendar_list_events(client, start_iso='2026-04-07T18:00:00', end_iso='2026-04-07T18:00:00')
    """
    arguments = {
        "start_iso": start_iso,
        "end_iso": end_iso,
        "calendar_id": calendar_id,
        "limit": limit,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "calendar_list_events", payload)
