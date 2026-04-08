from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def messages_get_conversation(
    client: MCPToolCaller,
    chat_id: str,
    limit: int | None = None,
    offset: int | None = None
) -> Any:
    """Messages Get Conversation

    Delegated Apple domain tool 'messages_get_conversation' exposed through Apple-Tools-MCP.

    Example:
        await messages_get_conversation(client, chat_id='example_chat_id', limit=1)
    """
    arguments = {
        "chat_id": chat_id,
        "limit": limit,
        "offset": offset,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "messages_get_conversation", payload)
