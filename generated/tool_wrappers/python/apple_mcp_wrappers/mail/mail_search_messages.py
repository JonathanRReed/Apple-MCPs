from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def mail_search_messages(
    client: MCPToolCaller,
    query: str,
    mailbox: str | None = None,
    unread_only: bool | None = None,
    limit: int | None = None,
    account: str | None = None
) -> Any:
    """Search Mail

    Search Apple Mail messages by query with optional account, mailbox and unread filters. Without account, accounts are searched in Mail's order and the limit can be filled by the first one; pass account (as returned by mail_list_mailboxes) to search a specific account.

    Example:
        await mail_search_messages(client, query='find mail', mailbox='example_mailbox')
    """
    arguments = {
        "query": query,
        "mailbox": mailbox,
        "unread_only": unread_only,
        "limit": limit,
        "account": account,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "mail_search_messages", payload)
