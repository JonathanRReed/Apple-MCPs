from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def reminders_list_lists(
    client: MCPToolCaller
) -> Any:
    """List Reminder Lists

    List available Apple Reminders lists.

    Example:
        await reminders_list_lists(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "reminders_list_lists", payload)
