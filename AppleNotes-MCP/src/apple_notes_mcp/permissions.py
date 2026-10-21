from apple_mcp_common.safety import safety_block_suggestion
from apple_notes_mcp.config import load_settings

SAFETY_ENV_VAR = "APPLE_NOTES_MCP_SAFETY_MODE"

READ_ACTIONS = frozenset(
    {
        "notes_health",
        "notes_list_accounts",
        "notes_list_folders",
        "notes_list_notes",
        "notes_get_note",
        "notes_search_notes",
        "notes_list_attachments",
    }
)
MANAGE_ACTIONS = frozenset(
    {
        "notes_create_note",
        "notes_update_note",
        "notes_append_to_note",
        "notes_delete_note",
        "notes_move_note",
        "notes_create_folder",
        "notes_rename_folder",
        "notes_delete_folder",
    }
)


class SafetyError(Exception):
    def __init__(self, error_code: str, message: str, suggestion: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.suggestion = suggestion


def ensure_action_allowed(action: str, account_name: str | None = None, folder_name: str | None = None) -> None:
    settings = load_settings()

    if action in READ_ACTIONS:
        if settings.allowed_accounts and account_name is not None and account_name not in settings.allowed_accounts:
            raise SafetyError("ACCOUNT_BLOCKED", f"Account '{account_name}' is not in the allowed account list.", "Use an account named in APPLE_NOTES_MCP_ALLOWED_ACCOUNTS, or ask the user to add this account to that setting (Claude Desktop: \"Allowed Notes accounts\" in the extension settings) or clear it, then restart the MCP client.")
        if settings.allowed_folders and folder_name is not None and folder_name not in settings.allowed_folders:
            raise SafetyError("FOLDER_BLOCKED", f"Folder '{folder_name}' is not in the allowed folder list.", "Use a folder named in APPLE_NOTES_MCP_ALLOWED_FOLDERS, or ask the user to add this folder to that setting (Claude Desktop: \"Allowed Notes folders\" in the extension settings) or clear it, then restart the MCP client.")
        return

    if action in MANAGE_ACTIONS:
        if settings.safety_mode == "safe_readonly":
            raise SafetyError("WRITE_BLOCKED", f"Action '{action}' is blocked because {SAFETY_ENV_VAR} is '{settings.safety_mode}'.", safety_block_suggestion(SAFETY_ENV_VAR, "safe_manage", settings.safety_mode))
        if settings.allowed_accounts and account_name is not None and account_name not in settings.allowed_accounts:
            raise SafetyError("ACCOUNT_BLOCKED", f"Account '{account_name}' is not in the allowed account list.", "Use an account named in APPLE_NOTES_MCP_ALLOWED_ACCOUNTS, or ask the user to add this account to that setting (Claude Desktop: \"Allowed Notes accounts\" in the extension settings) or clear it, then restart the MCP client.")
        if settings.allowed_folders and folder_name is not None and folder_name not in settings.allowed_folders:
            raise SafetyError("FOLDER_BLOCKED", f"Folder '{folder_name}' is not in the allowed folder list.", "Use a folder named in APPLE_NOTES_MCP_ALLOWED_FOLDERS, or ask the user to add this folder to that setting (Claude Desktop: \"Allowed Notes folders\" in the extension settings) or clear it, then restart the MCP client.")
        return

    raise SafetyError("UNKNOWN_ACTION", f"Action '{action}' is not recognized by the safety policy.", "Update the permissions layer before exposing new tools.")
