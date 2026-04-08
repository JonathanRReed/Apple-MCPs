from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def system_set_clipboard(
    client: MCPToolCaller,
    text: str
) -> Any:
    """Set Clipboard

    Write text into the macOS clipboard.

    Example:
        await system_set_clipboard(client, text='example_text')
    """
    arguments = {
        "text": text,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "system_set_clipboard", payload)
