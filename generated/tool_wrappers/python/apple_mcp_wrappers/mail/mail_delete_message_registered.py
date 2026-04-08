from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def mail_delete_message_registered(
    client: MCPToolCaller,
    message_id: str
) -> Any:
    """Delete Message

    Delete (trash) an email message by its message_id.

    Example:
        await mail_delete_message_registered(client, message_id='example_message_id')
    """
    arguments = {
        "message_id": message_id,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "mail_delete_message_registered", payload)
