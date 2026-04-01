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

MANAGE_ACTIONS = frozenset(
    {
        "contacts_create_contact",
        "contacts_update_contact",
    }
)

FULL_ACCESS_ACTIONS = frozenset(
    {
        "contacts_delete_contact",
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
    if action in MANAGE_ACTIONS:
        if settings.safety_mode == "safe_readonly":
            raise SafetyError(
                "WRITE_BLOCKED",
                f"Action '{action}' is blocked in safety mode '{settings.safety_mode}'.",
                "Switch to safe_manage or full_access to create/update contacts.",
            )
        return
    if action in FULL_ACCESS_ACTIONS:
        if settings.safety_mode != "full_access":
            raise SafetyError(
                "WRITE_BLOCKED",
                f"Action '{action}' requires full_access mode (current: '{settings.safety_mode}').",
                "Switch to full_access to delete contacts.",
            )
        return
    raise SafetyError(
        "UNKNOWN_ACTION",
        f"Action '{action}' is not recognized by the safety policy '{settings.safety_mode}'.",
        "Update the permissions layer before exposing new Contacts tools.",
    )
