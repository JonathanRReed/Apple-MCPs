from __future__ import annotations

from dataclasses import dataclass

from apple_system_mcp.config import load_settings


@dataclass(frozen=True)
class SafetyError(Exception):
    error_code: str
    message: str
    suggestion: str | None = None


READ_ONLY_ACTIONS = {
    "system_health",
    "system_status",
    "system_get_battery",
    "system_get_frontmost_app",
    "system_list_running_apps",
    "system_get_clipboard",
}

MANAGE_ACTIONS = {
    "system_set_clipboard",
    "system_show_notification",
    "system_open_application",
}


def ensure_action_allowed(action: str) -> None:
    safety_mode = load_settings().safety_mode
    if action in READ_ONLY_ACTIONS:
        return
    if action in MANAGE_ACTIONS and safety_mode in {"safe_manage", "full_access"}:
        return
    raise SafetyError(
        error_code="SAFETY_RESTRICTION",
        message=f"{action} is not allowed while APPLE_SYSTEM_MCP_SAFETY_MODE={safety_mode}.",
        suggestion="Use safe_manage or full_access for system mutation tools.",
    )
