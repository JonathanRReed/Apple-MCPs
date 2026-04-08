from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def mail_mark_message(
    client: MCPToolCaller,
    message_id: str,
    is_read: bool
) -> Any:
    """Mail Mark Message

    Delegated Apple domain tool 'mail_mark_message' exposed through Apple-Tools-MCP.

    Example:
        await mail_mark_message(client, message_id='example_message_id', is_read=False)
    """
    arguments = {
        "message_id": message_id,
        "is_read": is_read,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "mail_mark_message", payload)
