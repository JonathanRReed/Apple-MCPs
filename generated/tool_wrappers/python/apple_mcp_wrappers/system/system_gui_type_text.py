from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def system_gui_type_text(
    client: MCPToolCaller,
    text: str,
    application: str | None = None,
    bundle_id: str | None = None
) -> Any:
    """Type Text

    Type text into the frontmost focused control. This is a GUI fallback tool.

    Example:
        await system_gui_type_text(client, text='example_text', application='example_application')
    """
    arguments = {
        "text": text,
        "application": application,
        "bundle_id": bundle_id,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "system_gui_type_text", payload)
