from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def mail_send_message_registered(
    client: MCPToolCaller,
    to: list[Any],
    cc: list[Any] | None = None,
    bcc: list[Any] | None = None,
    subject: str | None = None,
    body: str | None = None,
    attachments: list[Any] | None = None,
    from_account: str | None = None
) -> Any:
    """Send Message

    Send an email immediately via Apple Mail. Optionally specify from_account as an email address or account name to set the sender.

    Example:
        await mail_send_message_registered(client, to=[], cc=[])
    """
    arguments = {
        "to": to,
        "cc": cc,
        "bcc": bcc,
        "subject": subject,
        "body": body,
        "attachments": attachments,
        "from_account": from_account,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "mail_send_message_registered", payload)
