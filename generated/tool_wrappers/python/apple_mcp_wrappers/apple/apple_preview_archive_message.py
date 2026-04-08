from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_preview_archive_message(
    client: MCPToolCaller,
    message_id: str,
    archive_mailbox: str | None = None,
    archive_account: str | None = None
) -> Any:
    """Apple Preview Archive Message

    Preview how Apple-Tools will archive a Mail message before moving it.

    Example:
        await apple_preview_archive_message(client, message_id='example_message_id', archive_mailbox='example_archive_mailbox')
    """
    arguments = {
        "message_id": message_id,
        "archive_mailbox": archive_mailbox,
        "archive_account": archive_account,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_preview_archive_message", payload)
