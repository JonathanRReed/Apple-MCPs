from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def contacts_delete_contact(
    client: MCPToolCaller,
    contact_id: str
) -> Any:
    """Contacts Delete Contact

    Delegated Apple domain tool 'contacts_delete_contact' exposed through Apple-Tools-MCP.

    Example:
        await contacts_delete_contact(client, contact_id='example_contact_id')
    """
    arguments = {
        "contact_id": contact_id,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "contacts_delete_contact", payload)
