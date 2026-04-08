from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def mail_mark_message_registered(
    client: MCPToolCaller,
    message_id: str,
    is_read: bool
) -> Any:
    """Mark Message Read/Unread

    Set the read status of an email message. Pass is_read=true to mark as read, is_read=false to mark as unread.

    Example:
        await mail_mark_message_registered(client, message_id='example_message_id', is_read=False)
    """
    arguments = {
        "message_id": message_id,
        "is_read": is_read,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "mail_mark_message_registered", payload)
