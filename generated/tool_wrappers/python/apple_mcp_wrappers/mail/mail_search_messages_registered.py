from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def mail_search_messages_registered(
    client: MCPToolCaller,
    query: str,
    mailbox: str | None = None,
    unread_only: bool | None = None,
    limit: int | None = None
) -> Any:
    """Search Messages

    Search Apple Mail messages by query with optional mailbox and unread filters.

    Example:
        await mail_search_messages_registered(client, query='find mail', mailbox='example_mailbox')
    """
    arguments = {
        "query": query,
        "mailbox": mailbox,
        "unread_only": unread_only,
        "limit": limit,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "mail_search_messages_registered", payload)
