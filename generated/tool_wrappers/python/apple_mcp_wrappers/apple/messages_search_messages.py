from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def messages_search_messages(
    client: MCPToolCaller,
    query: str,
    chat_id: str | None = None,
    sender: str | None = None,
    start_iso: str | None = None,
    end_iso: str | None = None,
    limit: int | None = None,
    offset: int | None = None
) -> Any:
    """Messages Search Messages

    Delegated Apple domain tool 'messages_search_messages' exposed through Apple-Tools-MCP.

    Example:
        await messages_search_messages(client, query='find apple', chat_id='example_chat_id')
    """
    arguments = {
        "query": query,
        "chat_id": chat_id,
        "sender": sender,
        "start_iso": start_iso,
        "end_iso": end_iso,
        "limit": limit,
        "offset": offset,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "messages_search_messages", payload)
