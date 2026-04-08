from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def mail_forward_message(
    client: MCPToolCaller,
    message_id: str,
    to: list[Any],
    body: str | None = None,
    from_account: str | None = None
) -> Any:
    """Mail Forward Message

    Delegated Apple domain tool 'mail_forward_message' exposed through Apple-Tools-MCP.

    Example:
        await mail_forward_message(client, message_id='example_message_id', to=[])
    """
    arguments = {
        "message_id": message_id,
        "to": to,
        "body": body,
        "from_account": from_account,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "mail_forward_message", payload)
