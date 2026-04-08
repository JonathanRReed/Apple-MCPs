from __future__ import annotations

from .client import MCPToolCaller

from .apple_get_preferences import apple_get_preferences
from .apple_detect_defaults import apple_detect_defaults
from .apple_update_preferences import apple_update_preferences
from .apple_detect_digest_folder import apple_detect_digest_folder
from .apple_set_digest_folder import apple_set_digest_folder
from .apple_ensure_digest_folder import apple_ensure_digest_folder
from .apple_update_contact_preferences import apple_update_contact_preferences
from .apple_prepare_communication import apple_prepare_communication
from .apple_preview_communication import apple_preview_communication
from .apple_preview_archive_message import apple_preview_archive_message
from .apple_preview_create_reminder_with_defaults import apple_preview_create_reminder_with_defaults
from .apple_preview_create_note_with_defaults import apple_preview_create_note_with_defaults
from .apple_preview_follow_up_from_mail import apple_preview_follow_up_from_mail
from .apple_send_communication import apple_send_communication
from .apple_archive_message import apple_archive_message
from .apple_list_recent_actions import apple_list_recent_actions
from .apple_undo_action import apple_undo_action
from .apple_create_reminder_with_defaults import apple_create_reminder_with_defaults
from .apple_create_note_with_defaults import apple_create_note_with_defaults
from .apple_capture_follow_up_from_mail import apple_capture_follow_up_from_mail
from .apple_event_collaboration_summary import apple_event_collaboration_summary
from .apple_maps_search_places_strict import apple_maps_search_places_strict
from .apple_maps_get_directions_strict import apple_maps_get_directions_strict
from .apple_find_duplicate_contacts import apple_find_duplicate_contacts
from .apple_prepare_unique_contact import apple_prepare_unique_contact
from .apple_list_shortcuts_for_capability import apple_list_shortcuts_for_capability
from .apple_route_or_run_shortcut import apple_route_or_run_shortcut
from .apple_open_application import apple_open_application
from .apple_get_focus_status import apple_get_focus_status
from .apple_get_system_context import apple_get_system_context
from .apple_open_file_path import apple_open_file_path
from .apple_reveal_in_finder import apple_reveal_in_finder
from .apple_tag_file import apple_tag_file
from .apple_update_system_setting import apple_update_system_setting
from .apple_control_frontmost_app import apple_control_frontmost_app
from .apple_suggest_mailboxes import apple_suggest_mailboxes
from .apple_suggest_calendars import apple_suggest_calendars
from .apple_suggest_reminder_lists import apple_suggest_reminder_lists
from .apple_suggest_shortcuts import apple_suggest_shortcuts
from .apple_suggest_contacts import apple_suggest_contacts
from .apple_suggest_note_folders import apple_suggest_note_folders
from .apple_suggest_message_conversations import apple_suggest_message_conversations
from .apple_suggest_files import apple_suggest_files
from .apple_suggest_running_apps import apple_suggest_running_apps
from .apple_suggest_places import apple_suggest_places
from .apple_permission_guide import apple_permission_guide
from .apple_recheck_permissions import apple_recheck_permissions
from .apple_send_message_interactive import apple_send_message_interactive
from .apple_create_event_interactive import apple_create_event_interactive
from .apple_health import apple_health
from .apple_overview import apple_overview
from .mail_health import mail_health
from .mail_list_mailboxes import mail_list_mailboxes
from .mail_search_messages import mail_search_messages
from .mail_get_message import mail_get_message
from .mail_get_thread import mail_get_thread
from .mail_compose_draft import mail_compose_draft
from .mail_reply_message import mail_reply_message
from .mail_reply_latest_in_thread import mail_reply_latest_in_thread
from .mail_forward_message import mail_forward_message
from .mail_mark_message import mail_mark_message
from .mail_move_message import mail_move_message
from .mail_archive_thread import mail_archive_thread
from .mail_delete_message import mail_delete_message
from .mail_send_message import mail_send_message
from .calendar_health import calendar_health
from .calendar_list_calendars import calendar_list_calendars
from .calendar_list_events import calendar_list_events
from .calendar_get_event import calendar_get_event
from .calendar_create_event import calendar_create_event
from .calendar_update_event import calendar_update_event
from .calendar_delete_event import calendar_delete_event
from .reminders_health import reminders_health
from .reminders_list_lists import reminders_list_lists
from .reminders_create_list import reminders_create_list
from .reminders_delete_list import reminders_delete_list
from .reminders_list_reminders import reminders_list_reminders
from .reminders_get_reminder import reminders_get_reminder
from .reminders_create_reminder import reminders_create_reminder
from .reminders_update_reminder import reminders_update_reminder
from .reminders_complete_reminder import reminders_complete_reminder
from .reminders_uncomplete_reminder import reminders_uncomplete_reminder
from .reminders_delete_reminder import reminders_delete_reminder
from .shortcuts_health import shortcuts_health
from .shortcuts_list_shortcuts import shortcuts_list_shortcuts
from .shortcuts_list_folders import shortcuts_list_folders
from .shortcuts_view_shortcut import shortcuts_view_shortcut
from .shortcuts_run_shortcut import shortcuts_run_shortcut
from .files_health import files_health
from .files_list_allowed_roots import files_list_allowed_roots
from .files_list_directory import files_list_directory
from .files_search_files import files_search_files
from .files_get_file_info import files_get_file_info
from .files_read_text_file import files_read_text_file
from .files_recent_files import files_recent_files
from .files_get_tags import files_get_tags
from .files_list_recent_locations import files_list_recent_locations
from .files_get_icloud_status import files_get_icloud_status
from .files_create_folder import files_create_folder
from .files_move_path import files_move_path
from .files_open_path import files_open_path
from .files_reveal_in_finder import files_reveal_in_finder
from .files_set_tags import files_set_tags
from .files_add_tags import files_add_tags
from .files_remove_tags import files_remove_tags
from .files_delete_path import files_delete_path
from .system_health import system_health
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
from .system_set_clipboard import system_set_clipboard
from .system_show_notification import system_show_notification
from .system_open_application import system_open_application
from .system_gui_list_menu_bar_items import system_gui_list_menu_bar_items
from .system_gui_click_menu_path import system_gui_click_menu_path
from .system_gui_press_keys import system_gui_press_keys
from .system_gui_type_text import system_gui_type_text
from .system_gui_click_button import system_gui_click_button
from .system_gui_choose_popup_value import system_gui_choose_popup_value
from .maps_health import maps_health
from .maps_search_places import maps_search_places
from .maps_get_directions import maps_get_directions
from .maps_build_maps_link import maps_build_maps_link
from .maps_open_directions_in_maps import maps_open_directions_in_maps
from .contacts_health import contacts_health
from .contacts_list_contacts import contacts_list_contacts
from .contacts_create_contact import contacts_create_contact
from .contacts_update_contact import contacts_update_contact
from .contacts_delete_contact import contacts_delete_contact
from .contacts_search_contacts import contacts_search_contacts
from .contacts_get_contact import contacts_get_contact
from .contacts_resolve_message_recipient import contacts_resolve_message_recipient
from .notes_health import notes_health
from .notes_list_accounts import notes_list_accounts
from .notes_list_folders import notes_list_folders
from .notes_list_notes import notes_list_notes
from .notes_get_note import notes_get_note
from .notes_search_notes import notes_search_notes
from .notes_create_note import notes_create_note
from .notes_append_to_note import notes_append_to_note
from .notes_update_note import notes_update_note
from .notes_delete_note import notes_delete_note
from .notes_move_note import notes_move_note
from .notes_create_folder import notes_create_folder
from .notes_rename_folder import notes_rename_folder
from .notes_delete_folder import notes_delete_folder
from .notes_list_attachments import notes_list_attachments
from .messages_health import messages_health
from .messages_list_conversations import messages_list_conversations
from .messages_get_conversation import messages_get_conversation
from .messages_search_messages import messages_search_messages
from .messages_get_message import messages_get_message
from .messages_list_attachments import messages_list_attachments
from .messages_send_message import messages_send_message
from .messages_reply_in_conversation import messages_reply_in_conversation
from .messages_send_attachment import messages_send_attachment
from .apple_list_prompts import apple_list_prompts
from .apple_get_prompt import apple_get_prompt
from .apple_generate_daily_briefing import apple_generate_daily_briefing
from .apple_generate_weekly_briefing import apple_generate_weekly_briefing
from .apple_triage_communications_task import apple_triage_communications_task

__all__ = [
    "apple_get_preferences",
    "apple_detect_defaults",
    "apple_update_preferences",
    "apple_detect_digest_folder",
    "apple_set_digest_folder",
    "apple_ensure_digest_folder",
    "apple_update_contact_preferences",
    "apple_prepare_communication",
    "apple_preview_communication",
    "apple_preview_archive_message",
    "apple_preview_create_reminder_with_defaults",
    "apple_preview_create_note_with_defaults",
    "apple_preview_follow_up_from_mail",
    "apple_send_communication",
    "apple_archive_message",
    "apple_list_recent_actions",
    "apple_undo_action",
    "apple_create_reminder_with_defaults",
    "apple_create_note_with_defaults",
    "apple_capture_follow_up_from_mail",
    "apple_event_collaboration_summary",
    "apple_maps_search_places_strict",
    "apple_maps_get_directions_strict",
    "apple_find_duplicate_contacts",
    "apple_prepare_unique_contact",
    "apple_list_shortcuts_for_capability",
    "apple_route_or_run_shortcut",
    "apple_open_application",
    "apple_get_focus_status",
    "apple_get_system_context",
    "apple_open_file_path",
    "apple_reveal_in_finder",
    "apple_tag_file",
    "apple_update_system_setting",
    "apple_control_frontmost_app",
    "apple_suggest_mailboxes",
    "apple_suggest_calendars",
    "apple_suggest_reminder_lists",
    "apple_suggest_shortcuts",
    "apple_suggest_contacts",
    "apple_suggest_note_folders",
    "apple_suggest_message_conversations",
    "apple_suggest_files",
    "apple_suggest_running_apps",
    "apple_suggest_places",
    "apple_permission_guide",
    "apple_recheck_permissions",
    "apple_send_message_interactive",
    "apple_create_event_interactive",
    "apple_health",
    "apple_overview",
    "mail_health",
    "mail_list_mailboxes",
    "mail_search_messages",
    "mail_get_message",
    "mail_get_thread",
    "mail_compose_draft",
    "mail_reply_message",
    "mail_reply_latest_in_thread",
    "mail_forward_message",
    "mail_mark_message",
    "mail_move_message",
    "mail_archive_thread",
    "mail_delete_message",
    "mail_send_message",
    "calendar_health",
    "calendar_list_calendars",
    "calendar_list_events",
    "calendar_get_event",
    "calendar_create_event",
    "calendar_update_event",
    "calendar_delete_event",
    "reminders_health",
    "reminders_list_lists",
    "reminders_create_list",
    "reminders_delete_list",
    "reminders_list_reminders",
    "reminders_get_reminder",
    "reminders_create_reminder",
    "reminders_update_reminder",
    "reminders_complete_reminder",
    "reminders_uncomplete_reminder",
    "reminders_delete_reminder",
    "shortcuts_health",
    "shortcuts_list_shortcuts",
    "shortcuts_list_folders",
    "shortcuts_view_shortcut",
    "shortcuts_run_shortcut",
    "files_health",
    "files_list_allowed_roots",
    "files_list_directory",
    "files_search_files",
    "files_get_file_info",
    "files_read_text_file",
    "files_recent_files",
    "files_get_tags",
    "files_list_recent_locations",
    "files_get_icloud_status",
    "files_create_folder",
    "files_move_path",
    "files_open_path",
    "files_reveal_in_finder",
    "files_set_tags",
    "files_add_tags",
    "files_remove_tags",
    "files_delete_path",
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
    "system_set_clipboard",
    "system_show_notification",
    "system_open_application",
    "system_gui_list_menu_bar_items",
    "system_gui_click_menu_path",
    "system_gui_press_keys",
    "system_gui_type_text",
    "system_gui_click_button",
    "system_gui_choose_popup_value",
    "maps_health",
    "maps_search_places",
    "maps_get_directions",
    "maps_build_maps_link",
    "maps_open_directions_in_maps",
    "contacts_health",
    "contacts_list_contacts",
    "contacts_create_contact",
    "contacts_update_contact",
    "contacts_delete_contact",
    "contacts_search_contacts",
    "contacts_get_contact",
    "contacts_resolve_message_recipient",
    "notes_health",
    "notes_list_accounts",
    "notes_list_folders",
    "notes_list_notes",
    "notes_get_note",
    "notes_search_notes",
    "notes_create_note",
    "notes_append_to_note",
    "notes_update_note",
    "notes_delete_note",
    "notes_move_note",
    "notes_create_folder",
    "notes_rename_folder",
    "notes_delete_folder",
    "notes_list_attachments",
    "messages_health",
    "messages_list_conversations",
    "messages_get_conversation",
    "messages_search_messages",
    "messages_get_message",
    "messages_list_attachments",
    "messages_send_message",
    "messages_reply_in_conversation",
    "messages_send_attachment",
    "apple_list_prompts",
    "apple_get_prompt",
    "apple_generate_daily_briefing",
    "apple_generate_weekly_briefing",
    "apple_triage_communications_task",
]
