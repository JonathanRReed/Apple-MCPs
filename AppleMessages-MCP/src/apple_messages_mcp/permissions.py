from apple_messages_mcp.config import load_settings

READ_ACTIONS = frozenset(
    {
        "messages_health",
        "messages_list_conversations",
        "messages_get_conversation",
        "messages_search_messages",
        "messages_get_message",
        "messages_list_attachments",
    }
)
MANAGE_ACTIONS = frozenset({"messages_send_message", "messages_reply_in_conversation", "messages_send_attachment"})


class SafetyError(Exception):
    def __init__(self, error_code: str, message: str, suggestion: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.suggestion = suggestion


def ensure_action_allowed(action: str) -> None:
    settings = load_settings()
    if action in READ_ACTIONS:
        return
    if action in MANAGE_ACTIONS:
        if settings.safety_mode == "safe_readonly":
            raise SafetyError(
                "WRITE_BLOCKED",
                f"Action '{action}' is blocked in safety mode '{settings.safety_mode}'.",
                "Switch to safe_manage or full_access to send or reply.",
            )
        return
    raise SafetyError(
        "UNKNOWN_ACTION",
        f"Action '{action}' is not recognized by the safety policy.",
        "Update the permissions layer before exposing new tools.",
    )
