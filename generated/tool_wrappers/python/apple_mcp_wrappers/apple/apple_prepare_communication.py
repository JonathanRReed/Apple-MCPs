from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_prepare_communication(
    client: MCPToolCaller,
    recipient: str,
    preferred_channel: str | None = None
) -> Any:
    """Apple Prepare Communication

    Resolve a recipient through Contacts, evaluate available channels, and return the recommended mail or messages target before sending.

    Example:
        await apple_prepare_communication(client, recipient='Jonathan Reed', preferred_channel='example_preferred_channel')
    """
    arguments = {
        "recipient": recipient,
        "preferred_channel": preferred_channel,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_prepare_communication", payload)
