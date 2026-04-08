from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def contacts_resolve_message_recipient(
    client: MCPToolCaller,
    query: str,
    channel: str | None = None
) -> Any:
    """Contacts Resolve Message Recipient

    Delegated Apple domain tool 'contacts_resolve_message_recipient' exposed through Apple-Tools-MCP.

    Example:
        await contacts_resolve_message_recipient(client, query='find apple', channel='example_channel')
    """
    arguments = {
        "query": query,
        "channel": channel,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "contacts_resolve_message_recipient", payload)
