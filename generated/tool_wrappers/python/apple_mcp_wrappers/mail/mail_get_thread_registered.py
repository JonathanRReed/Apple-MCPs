from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def mail_get_thread_registered(
    client: MCPToolCaller,
    message_id: str,
    limit: int | None = None
) -> Any:
    """Get Thread

    Find related messages in the same mailbox thread by normalized subject, anchored on a message_id.

    Example:
        await mail_get_thread_registered(client, message_id='example_message_id', limit=1)
    """
    arguments = {
        "message_id": message_id,
        "limit": limit,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "mail_get_thread_registered", payload)
