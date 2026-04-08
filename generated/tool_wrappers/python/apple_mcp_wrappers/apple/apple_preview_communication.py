from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_preview_communication(
    client: MCPToolCaller,
    recipient: str,
    message: str,
    preferred_channel: str | None = None,
    subject: str | None = None,
    attachments: list[Any] | None = None,
    from_account: str | None = None
) -> Any:
    """Apple Preview Communication

    Preview how Apple-Tools will route a communication before sending it through Messages or Mail.

    Example:
        await apple_preview_communication(client, recipient='Example Person', message='example_message')
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
    return await call_tool_json(client, "apple_preview_communication", payload)
