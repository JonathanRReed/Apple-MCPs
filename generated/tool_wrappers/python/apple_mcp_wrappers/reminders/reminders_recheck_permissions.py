from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def reminders_recheck_permissions(
    client: MCPToolCaller
) -> Any:
    """Reminders Recheck Permissions

    Recheck Reminders access after the user changes macOS permissions, and notify the client that Reminders resources changed.

    Example:
        await reminders_recheck_permissions(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "reminders_recheck_permissions", payload)
