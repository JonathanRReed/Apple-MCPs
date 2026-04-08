from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def mail_move_message_registered(
    client: MCPToolCaller,
    message_id: str,
    target_mailbox: str,
    target_account: str | None = None
) -> Any:
    """Move Message

    Move an email message to a different mailbox. Optionally specify target_account if the mailbox is in a different account.

    Example:
        await mail_move_message_registered(client, message_id='example_message_id', target_mailbox='example_target_mailbox')
    """
    arguments = {
        "message_id": message_id,
        "target_mailbox": target_mailbox,
        "target_account": target_account,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "mail_move_message_registered", payload)
