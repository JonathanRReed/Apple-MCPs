from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def reminders_list_reminders(
    client: MCPToolCaller,
    list_id: str | None = None,
    include_completed: bool | None = None,
    limit: int | None = None,
    search: str | None = None,
    due_after: str | None = None,
    due_before: str | None = None
) -> Any:
    """Reminders List Reminders

    Delegated Apple domain tool 'reminders_list_reminders' exposed through Apple-Tools-MCP.

    Example:
        await reminders_list_reminders(client, list_id='example_list_id', include_completed=False)
    """
    arguments = {
        "list_id": list_id,
        "include_completed": include_completed,
        "limit": limit,
        "search": search,
        "due_after": due_after,
        "due_before": due_before,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "reminders_list_reminders", payload)
