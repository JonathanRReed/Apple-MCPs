from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def system_gui_choose_popup_value(
    client: MCPToolCaller,
    label: str,
    value: str,
    description: str | None = None,
    application: str | None = None,
    bundle_id: str | None = None
) -> Any:
    """Choose Pop-Up Value

    Choose a value from a named pop-up button in the frontmost window. This is a GUI fallback tool.

    Example:
        await system_gui_choose_popup_value(client, label='example_label', value='example_value')
    """
    arguments = {
        "label": label,
        "value": value,
        "description": description,
        "application": application,
        "bundle_id": bundle_id,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "system_gui_choose_popup_value", payload)
