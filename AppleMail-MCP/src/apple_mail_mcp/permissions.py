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
    },
    SafetyProfile.SAFE_MANAGE: {
        "health",
        "mail_list_mailboxes",
        "mail_search_messages",
        "mail_get_message",
        "mail_compose_draft",
    },
    SafetyProfile.FULL_ACCESS: {
        "health",
        "mail_list_mailboxes",
        "mail_search_messages",
        "mail_get_message",
        "mail_compose_draft",
        "mail_send_message",
    },
}


def ensure_tool_allowed(profile: SafetyProfile, tool_name: str) -> None:
    allowed_tools = _ALLOWED_TOOLS.get(profile, set())
    if tool_name in allowed_tools:
        return
    raise SafetyPolicyError(f"Tool '{tool_name}' is blocked by safety profile '{profile.value}'.")
