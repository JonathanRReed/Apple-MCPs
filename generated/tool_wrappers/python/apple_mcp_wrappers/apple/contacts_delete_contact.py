from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def contacts_delete_contact(
    client: MCPToolCaller,
    contact_id: str
) -> Any:
    """Delete Contact

    Permanently delete a contact by contact_id. Requires full_access safety mode.

    Example:
        await contacts_delete_contact(client, contact_id='example_contact_id')
    """
    arguments = {
        "contact_id": contact_id,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "contacts_delete_contact", payload)
