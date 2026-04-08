from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def mail_reply_message(
    client: MCPToolCaller,
    message_id: str,
    body: str,
    reply_all: bool | None = None,
    from_account: str | None = None
) -> Any:
    """Mail Reply Message

    Delegated Apple domain tool 'mail_reply_message' exposed through Apple-Tools-MCP.

    Example:
        await mail_reply_message(client, message_id='example_message_id', body='example_body')
    """
    arguments = {
        "message_id": message_id,
        "body": body,
        "reply_all": reply_all,
        "from_account": from_account,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "mail_reply_message", payload)
