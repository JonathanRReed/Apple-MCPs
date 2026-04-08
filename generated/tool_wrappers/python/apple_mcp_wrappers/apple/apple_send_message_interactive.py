from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_send_message_interactive(
    client: MCPToolCaller,
    recipient: str | None = None,
    text: str | None = None
) -> Any:
    """Apple Send Message Interactive

    Send an Apple Messages message, asking for missing recipient or text when needed.

    Example:
        await apple_send_message_interactive(client, recipient='Jonathan Reed', text='example_text')
    """
    arguments = {
        "recipient": recipient,
        "text": text,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_send_message_interactive", payload)
