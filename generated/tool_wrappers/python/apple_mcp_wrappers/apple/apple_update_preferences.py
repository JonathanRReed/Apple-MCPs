from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_update_preferences(
    client: MCPToolCaller,
    default_mail_account: str | None = None,
    default_archive_mailbox: str | None = None,
    default_archive_account: str | None = None,
    default_calendar_id: str | None = None,
    default_calendar_name: str | None = None,
    default_reminder_list_id: str | None = None,
    default_reminder_list_name: str | None = None,
    default_notes_folder_id: str | None = None,
    default_notes_folder_name: str | None = None,
    default_notes_account_name: str | None = None,
    default_digest_folder_id: str | None = None,
    default_digest_folder_name: str | None = None,
    default_digest_account_name: str | None = None,
    preferred_communication_channel: str | None = None,
    preferred_message_channel: str | None = None
) -> Any:
    """Apple Update Preferences

    Persist assistant defaults such as default lists, folders, calendars, archive mailboxes, and preferred communication routing.

    Example:
        await apple_update_preferences(client, default_mail_account='example_default_mail_account', default_archive_mailbox='example_default_archive_mailbox')
    """
    arguments = {
        "default_mail_account": default_mail_account,
        "default_archive_mailbox": default_archive_mailbox,
        "default_archive_account": default_archive_account,
        "default_calendar_id": default_calendar_id,
        "default_calendar_name": default_calendar_name,
        "default_reminder_list_id": default_reminder_list_id,
        "default_reminder_list_name": default_reminder_list_name,
        "default_notes_folder_id": default_notes_folder_id,
        "default_notes_folder_name": default_notes_folder_name,
        "default_notes_account_name": default_notes_account_name,
        "default_digest_folder_id": default_digest_folder_id,
        "default_digest_folder_name": default_digest_folder_name,
        "default_digest_account_name": default_digest_account_name,
        "preferred_communication_channel": preferred_communication_channel,
        "preferred_message_channel": preferred_message_channel,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_update_preferences", payload)
