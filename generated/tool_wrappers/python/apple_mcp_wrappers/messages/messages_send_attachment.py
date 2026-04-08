from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def messages_send_attachment(
    client: MCPToolCaller,
    recipient: str,
    file_path: str,
    text: str | None = None
) -> Any:
    """Send Attachment

    Send a file attachment via Apple Messages to a recipient. Optionally include a text message.

    Example:
        await messages_send_attachment(client, recipient='Jonathan Reed', file_path='/path/to/item')
    """
    arguments = {
        "recipient": recipient,
        "file_path": file_path,
        "text": text,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "messages_send_attachment", payload)
