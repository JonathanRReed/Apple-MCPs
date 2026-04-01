from apple_reminders_mcp.config import load_settings

READ_ACTIONS = frozenset({"reminders_health", "reminders_list_lists", "reminders_list_reminders", "reminders_get_reminder"})
MANAGE_ACTIONS = frozenset(
    {
        "reminders_create_reminder",
        "reminders_update_reminder",
        "reminders_complete_reminder",
        "reminders_uncomplete_reminder",
        "reminders_create_list",
    }
)

FULL_ACCESS_ACTIONS = frozenset(
    {
        "reminders_delete_reminder",
        "reminders_delete_list",
    }
)


class SafetyError(Exception):
    def __init__(self, error_code: str, message: str, suggestion: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.suggestion = suggestion


def ensure_action_allowed(action: str, list_name: str | None = None) -> None:
    settings = load_settings()

    if action in READ_ACTIONS:
        if list_name is not None and settings.allowed_lists and list_name not in settings.allowed_lists:
            raise SafetyError(
                "LIST_BLOCKED",
                f"Reminder list '{list_name}' is not in the allowed list set.",
                "Choose one of the configured allowed lists or clear the allowlist.",
            )
        return

    if action in MANAGE_ACTIONS:
        if settings.safety_mode == "safe_readonly":
            raise SafetyError(
                "WRITE_BLOCKED",
                f"Action '{action}' is blocked in safety mode '{settings.safety_mode}'.",
                "Switch to safe_manage or full_access to mutate reminders.",
            )
        if list_name is not None and settings.allowed_lists and list_name not in settings.allowed_lists:
            raise SafetyError(
                "LIST_BLOCKED",
                f"Reminder list '{list_name}' is not in the allowed list set.",
                "Choose one of the configured allowed lists or clear the allowlist.",
            )
        return

    if action in FULL_ACCESS_ACTIONS:
        if settings.safety_mode != "full_access":
             raise SafetyError(
                "WRITE_BLOCKED",
                f"Action '{action}' requires full_access mode (current: '{settings.safety_mode}').",
                "Switch to full_access to delete reminders or lists.",
            )
        if list_name is not None and settings.allowed_lists and list_name not in settings.allowed_lists:
            raise SafetyError(
                "LIST_BLOCKED",
                f"Reminder list '{list_name}' is not in the allowed list set.",
                "Choose one of the configured allowed lists or clear the allowlist.",
            )
        return

    raise SafetyError(
        "UNKNOWN_ACTION",
        f"Action '{action}' is not recognized by the safety policy.",
        "Update the permissions layer before exposing new tools.",
    )
