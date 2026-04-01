from __future__ import annotations

from apple_mail_mcp.models import SafetyProfile


class SafetyPolicyError(Exception):
    pass


_ALLOWED_TOOLS: dict[SafetyProfile, set[str]] = {
    SafetyProfile.SAFE_READONLY: {
        "health",
        "mail_list_mailboxes",
        "mail_search_messages",
        "mail_get_message",
        "mail_get_thread",
    },
    SafetyProfile.SAFE_MANAGE: {
        "health",
        "mail_list_mailboxes",
        "mail_search_messages",
        "mail_get_message",
        "mail_compose_draft",
        "mail_mark_message",
        "mail_move_message",
        "mail_delete_message",
        "mail_reply_message",
        "mail_forward_message",
        "mail_get_thread",
        "mail_reply_latest_in_thread",
        "mail_archive_thread",
    },
    SafetyProfile.FULL_ACCESS: {
        "health",
        "mail_list_mailboxes",
        "mail_search_messages",
        "mail_get_message",
        "mail_compose_draft",
        "mail_send_message",
        "mail_mark_message",
        "mail_move_message",
        "mail_delete_message",
        "mail_reply_message",
        "mail_forward_message",
        "mail_get_thread",
        "mail_reply_latest_in_thread",
        "mail_archive_thread",
    },
}


def ensure_tool_allowed(profile: SafetyProfile, tool_name: str) -> None:
    allowed_tools = _ALLOWED_TOOLS.get(profile, set())
    if tool_name in allowed_tools:
        return
    raise SafetyPolicyError(f"Tool '{tool_name}' is blocked by safety profile '{profile.value}'.")
