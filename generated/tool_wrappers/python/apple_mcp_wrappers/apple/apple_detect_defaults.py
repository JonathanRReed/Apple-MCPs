from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_detect_defaults(
    client: MCPToolCaller,
    probe_apps: bool | None = None
) -> Any:
    """Apple Detect Defaults

    Read saved defaults without probing apps. Set probe_apps=true to discover and persist missing Mail, Calendar, Reminders, and Notes targets; this may open apps and request macOS permissions.

    Example:
        await apple_detect_defaults(client, probe_apps=False)
    """
    arguments = {
        "probe_apps": probe_apps,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_detect_defaults", payload)
