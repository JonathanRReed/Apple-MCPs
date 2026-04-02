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
    "system_list_settings_domains",
    "system_get_appearance_settings",
    "system_get_accessibility_settings",
    "system_get_dock_settings",
    "system_get_finder_settings",
    "system_get_settings_snapshot",
    "system_read_preference_domain",
}

MANAGE_ACTIONS = {
    "system_set_clipboard",
    "system_show_notification",
    "system_open_application",
    "system_set_appearance_mode",
    "system_set_show_all_extensions",
    "system_set_show_hidden_files",
    "system_set_finder_path_bar",
    "system_set_finder_status_bar",
    "system_set_dock_autohide",
    "system_set_dock_show_recents",
    "system_set_reduce_motion",
    "system_set_increase_contrast",
    "system_set_reduce_transparency",
    "system_gui_list_menu_bar_items",
    "system_gui_click_menu_path",
    "system_gui_press_keys",
    "system_gui_type_text",
    "system_gui_click_button",
    "system_gui_choose_popup_value",
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
