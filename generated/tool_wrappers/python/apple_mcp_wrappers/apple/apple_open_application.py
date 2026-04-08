from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_open_application(
    client: MCPToolCaller,
    application: str | None = None,
    bundle_id: str | None = None
) -> Any:
    """Apple Open Application

    Open an application through the unified Apple control plane using its name or bundle identifier.

    Example:
        await apple_open_application(client, application='example_application', bundle_id='example_bundle_id')
    """
    arguments = {
        "application": application,
        "bundle_id": bundle_id,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_open_application", payload)
