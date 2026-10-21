from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_control_frontmost_app(
    client: MCPToolCaller,
    action: str,
    application: str | None = None,
    bundle_id: str | None = None,
    menu_path: list[Any] | None = None,
    key: str | None = None,
    modifiers: list[Any] | None = None,
    text: str | None = None,
    label: str | None = None,
    description: str | None = None,
    index: int | None = None,
    value: str | None = None
) -> Any:
    """Apple Control Frontmost App

    Use the unified Apple control plane for bounded GUI fallback actions when a native app-domain tool cannot complete the task. Input actions (click_menu_path, press_keys, type_text, click_button, choose_popup_value) require application or bundle_id naming a running app whose bundle id is listed in APPLE_SYSTEM_MCP_GUI_ALLOWED_APPS (comma-separated bundle ids; GUI input is off while it is empty), and that app must come to the front before any input is sent. Terminals, script editors and automation apps are always refused, even if allow-listed.

    Example:
        await apple_control_frontmost_app(client, action='example_action', application='example_application')
    """
    arguments = {
        "action": action,
        "application": application,
        "bundle_id": bundle_id,
        "menu_path": menu_path,
        "key": key,
        "modifiers": modifiers,
        "text": text,
        "label": label,
        "description": description,
        "index": index,
        "value": value,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_control_frontmost_app", payload)
