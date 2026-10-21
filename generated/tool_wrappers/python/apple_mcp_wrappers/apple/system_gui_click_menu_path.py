from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def system_gui_click_menu_path(
    client: MCPToolCaller,
    menu_path: list[Any],
    application: str | None = None,
    bundle_id: str | None = None
) -> Any:
    """Click Menu Path

    Click a menu path in an application, for example ['File', 'New Window']. This is a GUI fallback tool.

    Example:
        await system_gui_click_menu_path(client, menu_path=[], application='example_application')
    """
    arguments = {
        "menu_path": menu_path,
        "application": application,
        "bundle_id": bundle_id,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "system_gui_click_menu_path", payload)
