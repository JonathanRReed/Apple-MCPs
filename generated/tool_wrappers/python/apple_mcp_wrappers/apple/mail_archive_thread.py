from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def mail_archive_thread(
    client: MCPToolCaller,
    message_id: str,
    archive_mailbox: str | None = None,
    archive_account: str | None = None,
    limit: int | None = None
) -> Any:
    """Mail Archive Thread

    Delegated Apple domain tool 'mail_archive_thread' exposed through Apple-Tools-MCP.

    Example:
        await mail_archive_thread(client, message_id='example_message_id', archive_mailbox='example_archive_mailbox')
    """
    arguments = {
        "message_id": message_id,
        "archive_mailbox": archive_mailbox,
        "archive_account": archive_account,
        "limit": limit,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "mail_archive_thread", payload)
