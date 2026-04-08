from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def mail_reply_latest_in_thread_registered(
    client: MCPToolCaller,
    message_id: str,
    body: str,
    reply_all: bool | None = None,
    from_account: str | None = None,
    limit: int | None = None
) -> Any:
    """Reply To Latest In Thread

    Find the latest related message in the same mailbox thread and reply to that message.

    Example:
        await mail_reply_latest_in_thread_registered(client, message_id='example_message_id', body='example_body')
    """
    arguments = {
        "message_id": message_id,
        "body": body,
        "reply_all": reply_all,
        "from_account": from_account,
        "limit": limit,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "mail_reply_latest_in_thread_registered", payload)
