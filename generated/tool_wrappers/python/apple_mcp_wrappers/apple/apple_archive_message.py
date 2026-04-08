from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_archive_message(
    client: MCPToolCaller,
    message_id: str,
    archive_mailbox: str | None = None,
    archive_account: str | None = None
) -> Any:
    """Apple Archive Message

    Move a message to the preferred archive mailbox, or auto-detect an archive mailbox if no preference exists yet.

    Example:
        await apple_archive_message(client, message_id='example_message_id', archive_mailbox='example_archive_mailbox')
    """
    arguments = {
        "message_id": message_id,
        "archive_mailbox": archive_mailbox,
        "archive_account": archive_account,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_archive_message", payload)
