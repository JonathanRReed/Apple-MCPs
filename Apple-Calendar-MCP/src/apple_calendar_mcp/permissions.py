from apple_calendar_mcp.config import load_settings
from apple_mcp_common.safety import safety_block_suggestion

SAFETY_ENV_VAR = "APPLE_CALENDAR_MCP_SAFETY_MODE"

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
                "Use a calendar listed in APPLE_CALENDAR_MCP_ALLOWED_CALENDARS, or ask the user to add this calendar to that setting (Claude Desktop: \"Allowed calendars\" in the extension settings) or clear it, then restart the MCP client.",
            )
        return

    if action in MANAGE_ACTIONS:
        if settings.safety_mode == "safe_readonly":
            raise SafetyError(
                "WRITE_BLOCKED",
                f"Action '{action}' is blocked because {SAFETY_ENV_VAR} is '{settings.safety_mode}'.",
                safety_block_suggestion(SAFETY_ENV_VAR, "safe_manage", settings.safety_mode),
            )
        if calendar_name is None and settings.allowed_calendars:
            raise SafetyError(
                "CALENDAR_BLOCKED",
                f"Action '{action}' has no resolvable target calendar, so it cannot be checked against the allowlist.",
                "Pass a calendar_id returned by calendar_list_calendars.",
            )
        if calendar_name is not None and settings.allowed_calendars and calendar_name not in settings.allowed_calendars:
            raise SafetyError(
                "CALENDAR_BLOCKED",
                f"Calendar '{calendar_name}' is not in the allowed calendar list.",
                "Use a calendar listed in APPLE_CALENDAR_MCP_ALLOWED_CALENDARS, or ask the user to add this calendar to that setting (Claude Desktop: \"Allowed calendars\" in the extension settings) or clear it, then restart the MCP client.",
            )
        if calendar_name is not None and settings.write_allowed_calendars and calendar_name not in settings.write_allowed_calendars:
            raise SafetyError(
                "CALENDAR_WRITE_BLOCKED",
                f"Calendar '{calendar_name}' is not in the write-allowed calendar list.",
                "Writes are restricted to APPLE_CALENDAR_MCP_WRITE_ALLOWED_CALENDARS; reading other calendars is still permitted. To write here, ask the user to add this calendar to that setting (Claude Desktop: \"Calendars the assistant may change\" in the extension settings), then restart the MCP client.",
            )
        if calendar_name is None and settings.write_allowed_calendars:
            # A write whose target calendar could not be resolved must fail closed: an
            # unresolvable name is exactly the case an allowlist exists to catch.
            raise SafetyError(
                "CALENDAR_WRITE_BLOCKED",
                f"Action '{action}' has no resolvable target calendar, so it cannot be checked against the write allowlist.",
                "Pass a calendar_id that resolves to one of APPLE_CALENDAR_MCP_WRITE_ALLOWED_CALENDARS.",
            )
        return

    raise SafetyError(
        "UNKNOWN_ACTION",
        f"Action '{action}' is not recognized by the safety policy.",
        "Update the permissions layer before exposing new tools.",
    )
