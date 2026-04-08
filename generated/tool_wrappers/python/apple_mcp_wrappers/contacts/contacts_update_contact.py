from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def contacts_update_contact(
    client: MCPToolCaller,
    contact_id: str,
    first_name: str | None = None,
    last_name: str | None = None,
    organization: str | None = None,
    phones: list[Any] | None = None,
    emails: list[Any] | None = None,
    note: str | None = None
) -> Any:
    """Update Contact

    Update an existing contact's information. Only the fields you provide will be changed.

    Example:
        await contacts_update_contact(client, contact_id='example_contact_id', first_name='example_first_name')
    """
    arguments = {
        "contact_id": contact_id,
        "first_name": first_name,
        "last_name": last_name,
        "organization": organization,
        "phones": phones,
        "emails": emails,
        "note": note,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "contacts_update_contact", payload)
