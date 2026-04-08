from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_update_contact_preferences(
    client: MCPToolCaller,
    contact_id: str,
    preferred_communication_channel: str | None = None,
    preferred_message_channel: str | None = None,
    preferred_mail_address: str | None = None,
    preferred_message_target: str | None = None,
    clear_existing: bool | None = None
) -> Any:
    """Apple Update Contact Preferences

    Persist preferred communication routing for a specific contact so Apple-Tools can choose the right channel and target for that person.

    Example:
        await apple_update_contact_preferences(client, contact_id='example_contact_id', preferred_communication_channel='example_preferred_communication_channel')
    """
    arguments = {
        "contact_id": contact_id,
        "preferred_communication_channel": preferred_communication_channel,
        "preferred_message_channel": preferred_message_channel,
        "preferred_mail_address": preferred_mail_address,
        "preferred_message_target": preferred_message_target,
        "clear_existing": clear_existing,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_update_contact_preferences", payload)
