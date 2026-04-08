from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def reminders_complete_reminder(
    client: MCPToolCaller,
    reminder_id: str
) -> Any:
    """Complete Reminder

    Mark a reminder as completed.

    Example:
        await reminders_complete_reminder(client, reminder_id='example_reminder_id')
    """
    arguments = {
        "reminder_id": reminder_id,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "reminders_complete_reminder", payload)
