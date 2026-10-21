from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def contacts_create_contact(
    client: MCPToolCaller,
    first_name: str,
    last_name: str | None = None,
    organization: str | None = None,
    phones: list[Any] | None = None,
    emails: list[Any] | None = None,
    note: str | None = None
) -> Any:
    """Create Contact

    Create a new contact in Apple Contacts with a first name (required) and optional last name, organization, and note.

    Example:
        await contacts_create_contact(client, first_name='example_first_name', last_name='example_last_name')
    """
    arguments = {
        "first_name": first_name,
        "last_name": last_name,
        "organization": organization,
        "phones": phones,
        "emails": emails,
        "note": note,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "contacts_create_contact", payload)
