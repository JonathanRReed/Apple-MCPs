from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def mail_search_messages(
    client: MCPToolCaller,
    query: str,
    mailbox: str | None = None,
    unread_only: bool | None = None,
    limit: int | None = None
) -> Any:
    """Mail Search Messages

    Delegated Apple domain tool 'mail_search_messages' exposed through Apple-Tools-MCP.

    Example:
        await mail_search_messages(client, query='find apple', mailbox='example_mailbox')
    """
    arguments = {
        "query": query,
        "mailbox": mailbox,
        "unread_only": unread_only,
        "limit": limit,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "mail_search_messages", payload)
