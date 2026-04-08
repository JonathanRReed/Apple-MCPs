from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def reminders_list_lists(
    client: MCPToolCaller
) -> Any:
    """Reminders List Lists

    Delegated Apple domain tool 'reminders_list_lists' exposed through Apple-Tools-MCP.

    Example:
        await reminders_list_lists(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "reminders_list_lists", payload)
