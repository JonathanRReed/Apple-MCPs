from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def contacts_get_contact(
    client: MCPToolCaller,
    contact_id: str
) -> Any:
    """Contacts Get Contact

    Delegated Apple domain tool 'contacts_get_contact' exposed through Apple-Tools-MCP.

    Example:
        await contacts_get_contact(client, contact_id='example_contact_id')
    """
    arguments = {
        "contact_id": contact_id,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "contacts_get_contact", payload)
