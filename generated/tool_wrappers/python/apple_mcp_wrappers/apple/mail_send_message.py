from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def mail_send_message(
    client: MCPToolCaller,
    to: list[Any],
    cc: list[Any] | None = None,
    bcc: list[Any] | None = None,
    subject: str | None = None,
    body: str | None = None,
    attachments: list[Any] | None = None,
    from_account: str | None = None
) -> Any:
    """Mail Send Message

    Delegated Apple domain tool 'mail_send_message' exposed through Apple-Tools-MCP.

    Example:
        await mail_send_message(client, to=[], cc=[])
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
    return await call_tool_json(client, "mail_send_message", payload)
