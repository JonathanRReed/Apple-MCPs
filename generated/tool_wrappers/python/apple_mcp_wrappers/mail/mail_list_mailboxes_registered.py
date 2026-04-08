from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def mail_list_mailboxes_registered(
    client: MCPToolCaller,
    account: str | None = None
) -> Any:
    """List Mailboxes

    List Apple Mail mailboxes, optionally filtered by account.

    Example:
        await mail_list_mailboxes_registered(client, account='example_account')
    """
    arguments = {
        "account": account,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "mail_list_mailboxes_registered", payload)
