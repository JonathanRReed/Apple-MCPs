from __future__ import annotations

from dataclasses import dataclass

from apple_files_mcp.config import load_settings


@dataclass(frozen=True)
class SafetyError(Exception):
    error_code: str
    message: str
    suggestion: str | None = None


READ_ONLY_ACTIONS = {
    "files_health",
    "files_list_allowed_roots",
    "files_list_directory",
    "files_search_files",
    "files_get_file_info",
    "files_read_text_file",
    "files_recent_files",
}

MANAGE_ACTIONS = {
    "files_create_folder",
    "files_move_path",
}

FULL_ACCESS_ACTIONS = {
    "files_delete_path",
}


def ensure_action_allowed(action: str) -> None:
    safety_mode = load_settings().safety_mode
    if action in READ_ONLY_ACTIONS:
        return
    if action in MANAGE_ACTIONS and safety_mode in {"safe_manage", "full_access"}:
        return
    if action in FULL_ACCESS_ACTIONS and safety_mode == "full_access":
        return
    raise SafetyError(
        error_code="SAFETY_RESTRICTION",
        message=f"{action} is not allowed while APPLE_FILES_MCP_SAFETY_MODE={safety_mode}.",
        suggestion="Use safe_manage for folder creation and moves, or full_access for deletes.",
    )
