from apple_contacts_mcp.config import load_settings

READ_ACTIONS = frozenset(
    {
        "contacts_health",
        "contacts_list_contacts",
        "contacts_search_contacts",
        "contacts_get_contact",
        "contacts_resolve_message_recipient",
    }
)


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
    raise SafetyError(
        "UNKNOWN_ACTION",
        f"Action '{action}' is not recognized by the safety policy '{settings.safety_mode}'.",
        "Update the permissions layer before exposing new Contacts tools.",
    )
