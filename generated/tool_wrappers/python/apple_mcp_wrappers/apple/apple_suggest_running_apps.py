from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_suggest_running_apps(
    client: MCPToolCaller,
    query: str | None = None,
    limit: int | None = None
) -> Any:
    """Apple Suggest Running Apps

    Apple Suggest Running Apps using the current Apple data surfaces. This is a completion fallback for clients without MCP completion support.

    Example:
        await apple_suggest_running_apps(client, query='find apple', limit=1)
    """
    arguments = {
        "query": query,
        "limit": limit,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_suggest_running_apps", payload)
