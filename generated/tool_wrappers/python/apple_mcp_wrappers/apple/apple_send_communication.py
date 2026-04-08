from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_send_communication(
    client: MCPToolCaller,
    recipient: str,
    message: str,
    preferred_channel: str | None = None,
    subject: str | None = None,
    attachments: list[Any] | None = None,
    from_account: str | None = None
) -> Any:
    """Apple Send Communication

    Send a communication through Messages or Mail using Contacts resolution and assistant defaults.

    Example:
        await apple_send_communication(client, recipient='Example Person', message='example_message')
    """
    arguments = {
        "recipient": recipient,
        "message": message,
        "preferred_channel": preferred_channel,
        "subject": subject,
        "attachments": attachments,
        "from_account": from_account,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_send_communication", payload)
