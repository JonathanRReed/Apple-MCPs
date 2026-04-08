from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def reminders_delete_list(
    client: MCPToolCaller,
    list_id: str
) -> Any:
    """Delete Reminder List

    Delete a reminder list entirely. Requires full_access safety mode.

    Example:
        await reminders_delete_list(client, list_id='example_list_id')
    """
    arguments = {
        "list_id": list_id,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "reminders_delete_list", payload)
