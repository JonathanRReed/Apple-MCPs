from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def system_gui_press_keys(
    client: MCPToolCaller,
    key: str,
    modifiers: list[Any] | None = None,
    application: str | None = None,
    bundle_id: str | None = None
) -> Any:
    """System Gui Press Keys

    Delegated Apple domain tool 'system_gui_press_keys' exposed through Apple-Tools-MCP.

    Example:
        await system_gui_press_keys(client, key='example_key', modifiers=[])
    """
    arguments = {
        "key": key,
        "modifiers": modifiers,
        "application": application,
        "bundle_id": bundle_id,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "system_gui_press_keys", payload)
