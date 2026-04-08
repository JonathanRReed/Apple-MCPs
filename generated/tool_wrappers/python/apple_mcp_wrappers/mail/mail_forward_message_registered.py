from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def mail_forward_message_registered(
    client: MCPToolCaller,
    message_id: str,
    to: list[Any],
    body: str | None = None,
    from_account: str | None = None
) -> Any:
    """Forward Message

    Forward an existing email message to new recipients. Provide a message_id and the to list. Optionally prepend body text and specify from_account.

    Example:
        await mail_forward_message_registered(client, message_id='example_message_id', to=[])
    """
    arguments = {
        "message_id": message_id,
        "to": to,
        "body": body,
        "from_account": from_account,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "mail_forward_message_registered", payload)
