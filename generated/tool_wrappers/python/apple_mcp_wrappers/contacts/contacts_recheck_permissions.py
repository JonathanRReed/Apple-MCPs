from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def contacts_recheck_permissions(
    client: MCPToolCaller
) -> Any:
    """Contacts Recheck Permissions

    Recheck Contacts access after the user changes macOS permissions, and notify the client that Contacts resources changed.

    Example:
        await contacts_recheck_permissions(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "contacts_recheck_permissions", payload)
