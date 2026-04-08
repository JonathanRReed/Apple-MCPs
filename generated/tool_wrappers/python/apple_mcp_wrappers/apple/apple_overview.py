from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_overview(
    client: MCPToolCaller
) -> Any:
    """Apple Overview

    Return an aggregated Apple ecosystem overview using the standalone domain resources.

    Example:
        await apple_overview(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_overview", payload)
