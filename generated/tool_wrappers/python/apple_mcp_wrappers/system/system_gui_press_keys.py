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
    """Press Keys

    Press a key or key chord in a named application. This is a GUI fallback tool. Requires application or bundle_id naming a running app whose bundle id is listed in APPLE_SYSTEM_MCP_GUI_ALLOWED_APPS (comma-separated bundle ids; GUI input is off while it is empty). Input is never sent to the frontmost app implicitly. Terminals, script editors and automation apps are always refused, even if allow-listed.

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
