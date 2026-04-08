from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def contacts_search_contacts(
    client: MCPToolCaller,
    query: str,
    limit: int | None = None
) -> Any:
    """Contacts Search Contacts

    Delegated Apple domain tool 'contacts_search_contacts' exposed through Apple-Tools-MCP.

    Example:
        await contacts_search_contacts(client, query='find apple', limit=1)
    """
    arguments = {
        "query": query,
        "limit": limit,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "contacts_search_contacts", payload)
