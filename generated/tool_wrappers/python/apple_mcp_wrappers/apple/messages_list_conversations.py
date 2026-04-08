from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def messages_list_conversations(
    client: MCPToolCaller,
    limit: int | None = None,
    offset: int | None = None,
    unread_only: bool | None = None
) -> Any:
    """Messages List Conversations

    Delegated Apple domain tool 'messages_list_conversations' exposed through Apple-Tools-MCP.

    Example:
        await messages_list_conversations(client, limit=1, offset=1)
    """
    arguments = {
        "limit": limit,
        "offset": offset,
        "unread_only": unread_only,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "messages_list_conversations", payload)
