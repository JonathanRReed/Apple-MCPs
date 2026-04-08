from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_preview_follow_up_from_mail(
    client: MCPToolCaller,
    message_id: str,
    due_date: str | None = None,
    reminder_title: str | None = None,
    note_title: str | None = None,
    create_reminder: bool | None = None,
    create_note: bool | None = None
) -> Any:
    """Apple Preview Follow-Up From Mail

    Preview how Apple-Tools will turn an email into a reminder and note before creating either item.

    Example:
        await apple_preview_follow_up_from_mail(client, message_id='example_message_id', due_date='2026-04-07T18:00:00')
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
    return await call_tool_json(client, "apple_preview_follow_up_from_mail", payload)
