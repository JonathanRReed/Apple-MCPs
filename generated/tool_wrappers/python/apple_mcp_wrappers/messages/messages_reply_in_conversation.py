from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def messages_reply_in_conversation(
    client: MCPToolCaller,
    chat_id: str,
    text: str,
    service_name: str | None = None
) -> Any:
    """Reply In Conversation

    Reply to an Apple Messages conversation using its chat_id. Supports both one-to-one and group chats. One-to-one replies use the service of the thread's latest message (SMS/RCS threads stay SMS/RCS) unless service_name is set.

    Example:
        await messages_reply_in_conversation(client, chat_id='example_chat_id', text='example_text')
    """
    arguments = {
        "chat_id": chat_id,
        "text": text,
        "service_name": service_name,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "messages_reply_in_conversation", payload)
