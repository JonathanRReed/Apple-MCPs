from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_permission_guide(
    client: MCPToolCaller,
    domain: str | None = None
) -> Any:
    """Apple Permission Guide

    Explain how to grant the Apple permissions needed by a given Apple domain on macOS.

    Example:
        await apple_permission_guide(client, domain='example_domain')
    """
    arguments = {
        "domain": domain,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_permission_guide", payload)
