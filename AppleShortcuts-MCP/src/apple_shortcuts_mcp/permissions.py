from apple_mcp_common.safety import safety_block_suggestion
from apple_shortcuts_mcp.config import load_settings

SAFETY_ENV_VAR = "APPLE_SHORTCUTS_MCP_SAFETY_MODE"

READ_ACTIONS = frozenset({"shortcuts_health", "shortcuts_list_shortcuts", "shortcuts_list_folders", "shortcuts_view_shortcut"})
MANAGE_ACTIONS = frozenset({"shortcuts_run_shortcut"})


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
                f"Action '{action}' is blocked because {SAFETY_ENV_VAR} is '{settings.safety_mode}'.",
                safety_block_suggestion(SAFETY_ENV_VAR, "safe_manage", settings.safety_mode),
            )
        return

    raise SafetyError(
        "UNKNOWN_ACTION",
        f"Action '{action}' is not recognized by the safety policy.",
        "Update the permissions layer before exposing new tools.",
    )
