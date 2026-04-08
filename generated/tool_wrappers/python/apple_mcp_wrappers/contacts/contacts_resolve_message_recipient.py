from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def contacts_resolve_message_recipient(
    client: MCPToolCaller,
    query: str,
    channel: str | None = None
) -> Any:
    """Resolve Message Recipient

    Resolve a contact into a message-ready phone number or email address.

    Example:
        await contacts_resolve_message_recipient(client, query='find contacts', channel='example_channel')
    """
    arguments = {
        "query": query,
        "channel": channel,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "contacts_resolve_message_recipient", payload)
