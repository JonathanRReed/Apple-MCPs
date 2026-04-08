from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def mail_get_message_registered(
    client: MCPToolCaller,
    message_id: str
) -> Any:
    """Get Message

    Fetch a single Apple Mail message by message_id.

    Example:
        await mail_get_message_registered(client, message_id='example_message_id')
    """
    arguments = {
        "message_id": message_id,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "mail_get_message_registered", payload)
