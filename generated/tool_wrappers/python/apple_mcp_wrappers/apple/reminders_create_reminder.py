from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def reminders_create_reminder(
    client: MCPToolCaller,
    title: str,
    list_id: str,
    notes: str | None = None,
    due_date: str | None = None,
    due_all_day: bool | None = None,
    remind_at: str | None = None,
    priority: int | None = None,
    parent_reminder_id: str | None = None,
    tags: list[Any] | None = None
) -> Any:
    """Reminders Create Reminder

    Delegated Apple domain tool 'reminders_create_reminder' exposed through Apple-Tools-MCP.

    Example:
        await reminders_create_reminder(client, title='example_title', list_id='example_list_id')
    """
    arguments = {
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
    return await call_tool_json(client, "reminders_create_reminder", payload)
