from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_preview_create_reminder_with_defaults(
    client: MCPToolCaller,
    title: str,
    due_date: str | None = None,
    notes: str | None = None,
    list_id: str | None = None,
    priority: int | None = None
) -> Any:
    """Apple Preview Create Reminder With Defaults

    Preview how Apple-Tools will create a reminder with the configured default reminder list.

    Example:
        await apple_preview_create_reminder_with_defaults(client, title='example_title', due_date='2026-04-07T18:00:00')
    """
    arguments = {
        "title": title,
        "due_date": due_date,
        "notes": notes,
        "list_id": list_id,
        "priority": priority,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_preview_create_reminder_with_defaults", payload)
