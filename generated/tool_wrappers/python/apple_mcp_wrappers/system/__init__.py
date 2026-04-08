from __future__ import annotations

from .client import MCPToolCaller

from .system_health import system_health
from .system_permission_guide import system_permission_guide
from .system_status import system_status
from .system_get_battery import system_get_battery
from .system_get_frontmost_app import system_get_frontmost_app
from .system_list_running_apps import system_list_running_apps
from .system_get_clipboard import system_get_clipboard
from .system_list_settings_domains import system_list_settings_domains
from .system_get_appearance_settings import system_get_appearance_settings
from .system_get_accessibility_settings import system_get_accessibility_settings
from .system_get_dock_settings import system_get_dock_settings
from .system_get_finder_settings import system_get_finder_settings
from .system_get_settings_snapshot import system_get_settings_snapshot
from .system_get_focus_status import system_get_focus_status
from .system_get_context_snapshot import system_get_context_snapshot
from .system_read_preference_domain import system_read_preference_domain
from .system_set_appearance_mode import system_set_appearance_mode
from .system_set_show_all_extensions import system_set_show_all_extensions
from .system_set_show_hidden_files import system_set_show_hidden_files
from .system_set_finder_path_bar import system_set_finder_path_bar
from .system_set_finder_status_bar import system_set_finder_status_bar
from .system_set_dock_autohide import system_set_dock_autohide
from .system_set_dock_show_recents import system_set_dock_show_recents
from .system_set_reduce_motion import system_set_reduce_motion
from .system_set_increase_contrast import system_set_increase_contrast
from .system_set_reduce_transparency import system_set_reduce_transparency
from .system_gui_list_menu_bar_items import system_gui_list_menu_bar_items
from .system_gui_click_menu_path import system_gui_click_menu_path
from .system_gui_press_keys import system_gui_press_keys
from .system_gui_type_text import system_gui_type_text
from .system_gui_click_button import system_gui_click_button
from .system_gui_choose_popup_value import system_gui_choose_popup_value
from .system_set_clipboard import system_set_clipboard
from .system_show_notification import system_show_notification
from .system_open_application import system_open_application
from .system_list_prompts import system_list_prompts
from .system_get_prompt_prompt import system_get_prompt_prompt

__all__ = [
    "system_health",
    "system_permission_guide",
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
    "system_get_focus_status",
    "system_get_context_snapshot",
    "system_read_preference_domain",
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
    "system_set_clipboard",
    "system_show_notification",
    "system_open_application",
    "system_list_prompts",
    "system_get_prompt_prompt",
]
