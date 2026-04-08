from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def reminders_delete_reminder(
    client: MCPToolCaller,
    reminder_id: str
) -> Any:
    """Delete Reminder

    Delete a reminder by reminder_id.

    Example:
        await reminders_delete_reminder(client, reminder_id='example_reminder_id')
    """
    arguments = {
        "reminder_id": reminder_id,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "reminders_delete_reminder", payload)
