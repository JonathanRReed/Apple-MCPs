from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def mail_get_thread(
    client: MCPToolCaller,
    message_id: str,
    limit: int | None = None
) -> Any:
    """Mail Get Thread

    Delegated Apple domain tool 'mail_get_thread' exposed through Apple-Tools-MCP.

    Example:
        await mail_get_thread(client, message_id='example_message_id', limit=1)
    """
    arguments = {
        "message_id": message_id,
        "limit": limit,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "mail_get_thread", payload)
