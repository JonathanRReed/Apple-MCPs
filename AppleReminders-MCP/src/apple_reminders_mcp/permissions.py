from apple_mcp_common.safety import safety_block_suggestion
from apple_reminders_mcp.config import load_settings

SAFETY_ENV_VAR = "APPLE_REMINDERS_MCP_SAFETY_MODE"

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
                "Use a list named in APPLE_REMINDERS_MCP_ALLOWED_LISTS, or ask the user to add this list to that setting (Claude Desktop: \"Allowed reminder lists\" in the extension settings) or clear it, then restart the MCP client.",
            )
        return

    if action in MANAGE_ACTIONS:
        if settings.safety_mode == "safe_readonly":
            raise SafetyError(
                "WRITE_BLOCKED",
                f"Action '{action}' is blocked because {SAFETY_ENV_VAR} is '{settings.safety_mode}'.",
                safety_block_suggestion(SAFETY_ENV_VAR, "safe_manage", settings.safety_mode),
            )
        if list_name is not None and settings.allowed_lists and list_name not in settings.allowed_lists:
            raise SafetyError(
                "LIST_BLOCKED",
                f"Reminder list '{list_name}' is not in the allowed list set.",
                "Use a list named in APPLE_REMINDERS_MCP_ALLOWED_LISTS, or ask the user to add this list to that setting (Claude Desktop: \"Allowed reminder lists\" in the extension settings) or clear it, then restart the MCP client.",
            )
        return

    if action in FULL_ACCESS_ACTIONS:
        if settings.safety_mode != "full_access":
            raise SafetyError(
                "WRITE_BLOCKED",
                f"Action '{action}' requires {SAFETY_ENV_VAR}=full_access (current: '{settings.safety_mode}').",
                safety_block_suggestion(SAFETY_ENV_VAR, "full_access", settings.safety_mode),
            )
        if list_name is not None and settings.allowed_lists and list_name not in settings.allowed_lists:
            raise SafetyError(
                "LIST_BLOCKED",
                f"Reminder list '{list_name}' is not in the allowed list set.",
                "Use a list named in APPLE_REMINDERS_MCP_ALLOWED_LISTS, or ask the user to add this list to that setting (Claude Desktop: \"Allowed reminder lists\" in the extension settings) or clear it, then restart the MCP client.",
            )
        return

    raise SafetyError(
        "UNKNOWN_ACTION",
        f"Action '{action}' is not recognized by the safety policy.",
        "Update the permissions layer before exposing new tools.",
    )
