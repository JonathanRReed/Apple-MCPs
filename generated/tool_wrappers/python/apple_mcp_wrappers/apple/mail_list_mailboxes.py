from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def mail_list_mailboxes(
    client: MCPToolCaller,
    account: str | None = None
) -> Any:
    """Mail List Mailboxes

    Delegated Apple domain tool 'mail_list_mailboxes' exposed through Apple-Tools-MCP.

    Example:
        await mail_list_mailboxes(client, account='example_account')
    """
    arguments = {
        "account": account,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "mail_list_mailboxes", payload)
