from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def system_gui_list_menu_bar_items(
    client: MCPToolCaller,
    application: str | None = None,
    bundle_id: str | None = None
) -> Any:
    """System Gui List Menu Bar Items

    Delegated Apple domain tool 'system_gui_list_menu_bar_items' exposed through Apple-Tools-MCP.

    Example:
        await system_gui_list_menu_bar_items(client, application='example_application', bundle_id='example_bundle_id')
    """
    arguments = {
        "application": application,
        "bundle_id": bundle_id,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "system_gui_list_menu_bar_items", payload)
