from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def notes_recheck_permissions(
    client: MCPToolCaller
) -> Any:
    """Notes Recheck Permissions

    Recheck Notes access after the user changes macOS permissions, and notify the client that Notes resources changed.

    Example:
        await notes_recheck_permissions(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "notes_recheck_permissions", payload)
