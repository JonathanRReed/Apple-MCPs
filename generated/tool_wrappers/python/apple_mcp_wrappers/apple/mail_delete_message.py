from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def mail_delete_message(
    client: MCPToolCaller,
    message_id: str
) -> Any:
    """Mail Delete Message

    Delegated Apple domain tool 'mail_delete_message' exposed through Apple-Tools-MCP.

    Example:
        await mail_delete_message(client, message_id='example_message_id')
    """
    arguments = {
        "message_id": message_id,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "mail_delete_message", payload)
