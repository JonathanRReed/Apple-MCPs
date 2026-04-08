from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_list_shortcuts_for_capability(
    client: MCPToolCaller,
    query: str,
    limit: int | None = None
) -> Any:
    """Apple List Shortcuts For Capability

    List likely shortcuts for a requested capability so Apple-Tools can use Shortcuts as an intentional bridge when native coverage is missing.

    Example:
        await apple_list_shortcuts_for_capability(client, query='find apple', limit=1)
    """
    arguments = {
        "query": query,
        "limit": limit,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_list_shortcuts_for_capability", payload)
