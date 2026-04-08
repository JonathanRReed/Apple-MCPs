from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_update_system_setting(
    client: MCPToolCaller,
    setting: str,
    enabled: bool | None = None,
    mode: str | None = None
) -> Any:
    """Apple Update System Setting

    Apply an assistant-relevant macOS setting through the unified Apple control plane.

    Example:
        await apple_update_system_setting(client, setting='example_setting', enabled=False)
    """
    arguments = {
        "setting": setting,
        "enabled": enabled,
        "mode": mode,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_update_system_setting", payload)
