from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def reminders_update_reminder(
    client: MCPToolCaller,
    reminder_id: str,
    title: str | None = None,
    list_id: str | None = None,
    notes: str | None = None,
    due_date: str | None = None,
    due_all_day: bool | None = None,
    remind_at: str | None = None,
    priority: int | None = None,
    parent_reminder_id: str | None = None,
    tags: list[Any] | None = None
) -> Any:
    """Update Reminder

    Update one or more fields on an existing reminder.

    Example:
        await reminders_update_reminder(client, reminder_id='example_reminder_id', title='example_title')
    """
    arguments = {
        "reminder_id": reminder_id,
        "title": title,
        "list_id": list_id,
        "notes": notes,
        "due_date": due_date,
        "due_all_day": due_all_day,
        "remind_at": remind_at,
        "priority": priority,
        "parent_reminder_id": parent_reminder_id,
        "tags": tags,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "reminders_update_reminder", payload)
