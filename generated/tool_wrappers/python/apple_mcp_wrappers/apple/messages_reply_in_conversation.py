from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def messages_reply_in_conversation(
    client: MCPToolCaller,
    chat_id: str,
    text: str
) -> Any:
    """Messages Reply In Conversation

    Delegated Apple domain tool 'messages_reply_in_conversation' exposed through Apple-Tools-MCP.

    Example:
        await messages_reply_in_conversation(client, chat_id='example_chat_id', text='example_text')
    """
    arguments = {
        "chat_id": chat_id,
        "text": text,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "messages_reply_in_conversation", payload)
