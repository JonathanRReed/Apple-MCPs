from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def reminders_uncomplete_reminder(
    client: MCPToolCaller,
    reminder_id: str
) -> Any:
    """Reminders Uncomplete Reminder

    Delegated Apple domain tool 'reminders_uncomplete_reminder' exposed through Apple-Tools-MCP.

    Example:
        await reminders_uncomplete_reminder(client, reminder_id='example_reminder_id')
    """
    arguments = {
        "reminder_id": reminder_id,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "reminders_uncomplete_reminder", payload)
