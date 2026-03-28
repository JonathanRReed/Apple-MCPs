from apple_notes_mcp.config import load_settings

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
            raise SafetyError("ACCOUNT_BLOCKED", f"Account '{account_name}' is not in the allowed account list.", "Choose one of the configured allowed accounts or clear the allowlist.")
        if settings.allowed_folders and folder_name is not None and folder_name not in settings.allowed_folders:
            raise SafetyError("FOLDER_BLOCKED", f"Folder '{folder_name}' is not in the allowed folder list.", "Choose one of the configured allowed folders or clear the allowlist.")
        return

    if action in MANAGE_ACTIONS:
        if settings.safety_mode == "safe_readonly":
            raise SafetyError("WRITE_BLOCKED", f"Action '{action}' is blocked in safety mode '{settings.safety_mode}'.", "Switch to safe_manage or full_access to mutate notes.")
        if settings.allowed_accounts and account_name is not None and account_name not in settings.allowed_accounts:
            raise SafetyError("ACCOUNT_BLOCKED", f"Account '{account_name}' is not in the allowed account list.", "Choose one of the configured allowed accounts or clear the allowlist.")
        if settings.allowed_folders and folder_name is not None and folder_name not in settings.allowed_folders:
            raise SafetyError("FOLDER_BLOCKED", f"Folder '{folder_name}' is not in the allowed folder list.", "Choose one of the configured allowed folders or clear the allowlist.")
        return

    raise SafetyError("UNKNOWN_ACTION", f"Action '{action}' is not recognized by the safety policy.", "Update the permissions layer before exposing new tools.")
