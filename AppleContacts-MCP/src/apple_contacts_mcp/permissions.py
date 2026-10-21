from apple_contacts_mcp.config import load_settings
from apple_mcp_common.safety import safety_block_suggestion

SAFETY_ENV_VAR = "APPLE_CONTACTS_MCP_SAFETY_MODE"

READ_ACTIONS = frozenset(
    {
        "contacts_health",
        "contacts_list_contacts",
        "contacts_search_contacts",
        "contacts_get_contact",
        "contacts_resolve_message_recipient",
        "contacts_find_duplicates",
        "contacts_suggest_merge_candidates",
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
                f"Action '{action}' is blocked because {SAFETY_ENV_VAR} is '{settings.safety_mode}'.",
                safety_block_suggestion(SAFETY_ENV_VAR, "safe_manage", settings.safety_mode),
            )
        return
    if action in FULL_ACCESS_ACTIONS:
        if settings.safety_mode != "full_access":
            raise SafetyError(
                "WRITE_BLOCKED",
                f"Action '{action}' requires {SAFETY_ENV_VAR}=full_access (current: '{settings.safety_mode}').",
                safety_block_suggestion(SAFETY_ENV_VAR, "full_access", settings.safety_mode),
            )
        return
    raise SafetyError(
        "UNKNOWN_ACTION",
        f"Action '{action}' is not recognized by the safety policy '{settings.safety_mode}'.",
        "Update the permissions layer before exposing new Contacts tools.",
    )
