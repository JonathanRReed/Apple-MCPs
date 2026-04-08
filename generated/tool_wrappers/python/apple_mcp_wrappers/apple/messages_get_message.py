from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def messages_get_message(
    client: MCPToolCaller,
    message_id: str
) -> Any:
    """Messages Get Message

    Delegated Apple domain tool 'messages_get_message' exposed through Apple-Tools-MCP.

    Example:
        await messages_get_message(client, message_id='example_message_id')
    """
    arguments = {
        "message_id": message_id,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "messages_get_message", payload)
