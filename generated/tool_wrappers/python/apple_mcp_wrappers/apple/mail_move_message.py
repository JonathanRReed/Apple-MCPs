from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def mail_move_message(
    client: MCPToolCaller,
    message_id: str,
    target_mailbox: str,
    target_account: str | None = None
) -> Any:
    """Mail Move Message

    Delegated Apple domain tool 'mail_move_message' exposed through Apple-Tools-MCP.

    Example:
        await mail_move_message(client, message_id='example_message_id', target_mailbox='example_target_mailbox')
    """
    arguments = {
        "message_id": message_id,
        "target_mailbox": target_mailbox,
        "target_account": target_account,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "mail_move_message", payload)
