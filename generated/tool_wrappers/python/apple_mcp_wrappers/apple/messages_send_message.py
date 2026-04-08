from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def messages_send_message(
    client: MCPToolCaller,
    recipient: str,
    text: str
) -> Any:
    """Messages Send Message

    Delegated Apple domain tool 'messages_send_message' exposed through Apple-Tools-MCP.

    Example:
        await messages_send_message(client, recipient='Example Person', text='example_text')
    """
    arguments = {
        "recipient": recipient,
        "text": text,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "messages_send_message", payload)
