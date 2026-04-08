from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def mail_compose_draft(
    client: MCPToolCaller,
    to: list[Any],
    cc: list[Any] | None = None,
    bcc: list[Any] | None = None,
    subject: str | None = None,
    body: str | None = None,
    attachments: list[Any] | None = None,
    from_account: str | None = None
) -> Any:
    """Mail Compose Draft

    Delegated Apple domain tool 'mail_compose_draft' exposed through Apple-Tools-MCP.

    Example:
        await mail_compose_draft(client, to=[], cc=[])
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
    return await call_tool_json(client, "mail_compose_draft", payload)
