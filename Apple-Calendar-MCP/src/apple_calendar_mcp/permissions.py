from apple_calendar_mcp.config import load_settings

READ_ACTIONS = frozenset({"calendar_health", "calendar_list_calendars", "calendar_list_events", "calendar_get_event"})
MANAGE_ACTIONS = frozenset({"calendar_create_event", "calendar_update_event", "calendar_delete_event"})


class SafetyError(Exception):
    def __init__(self, error_code: str, message: str, suggestion: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.suggestion = suggestion


def ensure_action_allowed(action: str, calendar_name: str | None = None) -> None:
    settings = load_settings()

    if action in READ_ACTIONS:
        if calendar_name is not None and settings.allowed_calendars and calendar_name not in settings.allowed_calendars:
            raise SafetyError(
                "CALENDAR_BLOCKED",
                f"Calendar '{calendar_name}' is not in the allowed calendar list.",
                "Choose one of the configured allowed calendars or clear the allowlist.",
            )
        return

    if action in MANAGE_ACTIONS:
        if settings.safety_mode == "safe_readonly":
            raise SafetyError(
                "WRITE_BLOCKED",
                f"Action '{action}' is blocked in safety mode '{settings.safety_mode}'.",
                "Switch to safe_manage or full_access to create events.",
            )
        if calendar_name is not None and settings.allowed_calendars and calendar_name not in settings.allowed_calendars:
            raise SafetyError(
                "CALENDAR_BLOCKED",
                f"Calendar '{calendar_name}' is not in the allowed calendar list.",
                "Choose one of the configured allowed calendars or clear the allowlist.",
            )
        return

    raise SafetyError(
        "UNKNOWN_ACTION",
        f"Action '{action}' is not recognized by the safety policy.",
        "Update the permissions layer before exposing new tools.",
    )
