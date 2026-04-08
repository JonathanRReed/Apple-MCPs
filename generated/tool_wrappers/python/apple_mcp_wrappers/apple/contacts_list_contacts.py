from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def contacts_list_contacts(
    client: MCPToolCaller,
    limit: int | None = None,
    offset: int | None = None
) -> Any:
    """Contacts List Contacts

    Delegated Apple domain tool 'contacts_list_contacts' exposed through Apple-Tools-MCP.

    Example:
        await contacts_list_contacts(client, limit=1, offset=1)
    """
    arguments = {
        "limit": limit,
        "offset": offset,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "contacts_list_contacts", payload)
