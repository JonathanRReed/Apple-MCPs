from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_capture_follow_up_from_mail(
    client: MCPToolCaller,
    message_id: str,
    due_date: str | None = None,
    reminder_title: str | None = None,
    note_title: str | None = None,
    create_reminder: bool | None = None,
    create_note: bool | None = None
) -> Any:
    """Apple Capture Follow-Up From Mail

    Turn an email into a reminder and an archival note using assistant defaults for the destination list and notes folder.

    Example:
        await apple_capture_follow_up_from_mail(client, message_id='example_message_id', due_date='2026-04-07T18:00:00')
    """
    arguments = {
        "message_id": message_id,
        "due_date": due_date,
        "reminder_title": reminder_title,
        "note_title": note_title,
        "create_reminder": create_reminder,
        "create_note": create_note,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_capture_follow_up_from_mail", payload)
