from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def messages_list_attachments(
    client: MCPToolCaller,
    chat_id: str | None = None,
    message_id: str | None = None,
    limit: int | None = None,
    offset: int | None = None
) -> Any:
    """Messages List Attachments

    Delegated Apple domain tool 'messages_list_attachments' exposed through Apple-Tools-MCP.

    Example:
        await messages_list_attachments(client, chat_id='example_chat_id', message_id='example_message_id')
    """
    arguments = {
        "chat_id": chat_id,
        "message_id": message_id,
        "limit": limit,
        "offset": offset,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "messages_list_attachments", payload)
