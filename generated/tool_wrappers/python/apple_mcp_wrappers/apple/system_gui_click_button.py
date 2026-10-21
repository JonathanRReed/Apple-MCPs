from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def system_gui_click_button(
    client: MCPToolCaller,
    label: str | None = None,
    description: str | None = None,
    index: int | None = None,
    application: str | None = None,
    bundle_id: str | None = None
) -> Any:
    """Click Button

    Click a named button in the frontmost window. This is a GUI fallback tool.

    Example:
        await system_gui_click_button(client, label='example_label', description='example_description')
    """
    arguments = {
        "label": label,
        "description": description,
        "index": index,
        "application": application,
        "bundle_id": bundle_id,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "system_gui_click_button", payload)
