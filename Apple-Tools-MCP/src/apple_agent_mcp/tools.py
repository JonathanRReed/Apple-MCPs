from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime, timedelta
from html import escape as html_escape
import json
import logging
import os
from pathlib import Path
import re
from typing import Any, Callable
from uuid import uuid4

from mcp import types
from mcp.server.experimental.task_context import ServerTaskContext
from mcp.server.fastmcp import Context, FastMCP
from mcp.types import Annotations, ToolAnnotations
from pydantic import AnyUrl, BaseModel, TypeAdapter

from apple_agent_mcp.bootstrap import ensure_domain_paths
from apple_agent_mcp.conformance import enable_conformance_mode
from apple_agent_mcp.config import load_settings
from apple_agent_mcp.models import (
    ActionHistoryResponse,
    ActionPreviewResponse,
    ActionUndoResponse,
    AppleErrorResponse,
    AppleHealthResponse,
    AppleOverviewResponse,
    AppleToolError,
    AssistantActionRecord,
    AssistantPreferences,
    CommunicationActionResponse,
    CommunicationPlanResponse,
    ContactRoutingPreference,
    EventCollaborationResponse,
    MailFollowupResponse,
    PermissionGuideResponse,
    PreferencesDetectResponse,
    PreferencesResponse,
    SuggestionListResponse,
)
from apple_agent_mcp.state import StateStoreError, load_action_history, load_preferences, save_action_history, save_preferences

ensure_domain_paths()

from apple_calendar_mcp.tools import (  # noqa: E402
    calendar_calendars_resource,
    calendar_create_event,
    calendar_delete_event,
    calendar_events_today_resource,
    calendar_get_event,
    calendar_health,
    calendar_list_calendars,
    calendar_list_events,
    calendar_plan_today_prompt,
    calendar_prepare_agenda_prompt,
    calendar_update_event,
)
from apple_calendar_mcp.models import ErrorResponse as CalendarErrorResponse, EventResponse, ToolError as CalendarToolError  # noqa: E402
from apple_mail_mcp.mail_bridge import AppleMailBridge  # noqa: E402
from apple_mail_mcp.models import (  # noqa: E402
    DraftRecord as MailDraftRecord,
    ErrorResponse as MailErrorResponse,
    HealthResponse as MailHealthResponse,
    MailboxListResponse as MailboxListResponse,
    MessageRecord as MailMessageRecord,
    MessageSearchResponse as MailMessageSearchResponse,
    SendRecord as MailSendRecord,
    ReplyRecord as MailReplyRecord,
    ForwardRecord as MailForwardRecord,
    MarkRecord as MailMarkRecord,
    MoveRecord as MailMoveRecord,
    DeleteRecord as MailDeleteRecord,
    ThreadMutationRecord as MailThreadMutationRecord,
    ThreadRecord as MailThreadRecord,
)
from apple_mail_mcp.tools import (  # noqa: E402
    mail_compose_draft as _mail_compose_draft,
    mail_draft_reply_prompt_text,
    mail_get_message as _mail_get_message,
    mail_get_thread as _mail_get_thread,
    mail_health as _mail_health,
    mail_inbox_triage_prompt_text,
    mail_list_mailboxes as _mail_list_mailboxes,
    mail_reply_latest_in_thread as _mail_reply_latest_in_thread,
    mail_reply_message as _mail_reply_message,
    mail_archive_thread as _mail_archive_thread,
    mail_forward_message as _mail_forward_message,
    mail_mark_message as _mail_mark_message,
    mail_move_message as _mail_move_message,
    mail_delete_message as _mail_delete_message,
    mail_search_messages as _mail_search_messages,
    mail_send_message as _mail_send_message,
    mailboxes_resource_tool,
)
from apple_messages_mcp.tools import (  # noqa: E402
    messages_conversation_resource,
    messages_draft_reply_prompt,
    messages_get_conversation as _messages_get_conversation,
    messages_get_message,
    messages_health,
    messages_list_attachments,
    messages_list_conversations,
    messages_recent_resource,
    messages_reply_in_conversation,
    messages_send_attachment as _messages_send_attachment,
    messages_search_messages,
    messages_send_message,
    messages_summarize_thread_prompt,
    messages_triage_unread_prompt,
    messages_unread_resource,
)
from apple_messages_mcp.models import ConversationResponse, ErrorResponse as MessagesErrorResponse, SendResponse, ToolError as MessagesToolError  # noqa: E402
from apple_contacts_mcp.tools import (  # noqa: E402
    contacts_contact_resource,
    contacts_directory_resource,
    contacts_get_contact,
    contacts_health,
    contacts_list_contacts,
    contacts_create_contact as _contacts_create_contact,
    contacts_update_contact as _contacts_update_contact,
    contacts_delete_contact as _contacts_delete_contact,
    contacts_prepare_message_recipient_prompt,
    contacts_resolve_message_recipient,
    contacts_search_contacts,
)
from apple_contacts_mcp.models import ErrorResponse as ContactsErrorResponse, ContactMethod, CreateContactResponse, ContactResponse, DeleteContactResponse  # noqa: E402
from apple_notes_mcp.tools import (  # noqa: E402
    notes_cleanup_prompt,
    notes_create_folder,
    notes_create_from_conversation_prompt,
    notes_create_note,
    notes_append_to_note as _notes_append_to_note,
    notes_delete_folder,
    notes_delete_note,
    notes_find_reference_prompt,
    notes_folders_resource,
    notes_get_note,
    notes_health,
    notes_list_accounts,
    notes_list_attachments,
    notes_list_folders,
    notes_list_notes,
    notes_move_note,
    notes_note_resource,
    notes_organize_topic_prompt,
    notes_recent_resource,
    notes_rename_folder,
    notes_search_notes,
    notes_update_note,
)
from apple_notes_mcp.models import NoteResponse as NotesNoteResponse, ErrorResponse as NotesErrorResponse  # noqa: E402
from apple_reminders_mcp.tools import (  # noqa: E402
    reminders_complete_reminder,
    reminders_create_reminder,
    reminders_delete_reminder,
    reminders_get_reminder,
    reminders_health,
    reminders_inbox_triage_prompt,
    reminders_list_lists,
    reminders_create_list as _reminders_create_list,
    reminders_delete_list as _reminders_delete_list,
    reminders_list_reminders,
    reminders_lists_resource,
    reminders_plan_today_prompt,
    reminders_today_resource,
    reminders_uncomplete_reminder,
    reminders_update_reminder,
)
from apple_reminders_mcp.models import DeleteReminderListResponse, ErrorResponse as RemindersErrorResponse, ReminderListMutationResponse, ReminderResponse as RemindersReminderResponse  # noqa: E402
from apple_shortcuts_mcp.tools import (  # noqa: E402
    shortcuts_all_resource,
    shortcuts_choose_and_run_prompt,
    shortcuts_follow_up_prompt,
    shortcuts_folder_resource,
    shortcuts_health,
    shortcuts_list_folders,
    shortcuts_list_shortcuts,
    shortcuts_run_shortcut,
    shortcuts_run_with_input_prompt,
    shortcuts_view_shortcut,
)
from apple_files_mcp.tools import (  # noqa: E402
    files_allowed_roots_resource,
    files_create_folder,
    files_delete_path,
    files_get_file_info,
    files_health,
    files_list_allowed_roots,
    files_list_directory,
    files_move_path,
    files_organize_workspace_prompt,
    files_prepare_attachment_prompt,
    files_read_text_file,
    files_recent_files,
    files_recent_resource,
    files_search_files,
)
from apple_system_mcp.tools import (  # noqa: E402
    system_applications_resource,
    system_capture_context_prompt,
    system_gui_choose_popup_value,
    system_gui_click_button,
    system_gui_click_menu_path,
    system_gui_list_menu_bar_items,
    system_gui_press_keys,
    system_gui_type_text,
    system_get_accessibility_settings,
    system_get_battery,
    system_get_clipboard,
    system_get_dock_settings,
    system_get_finder_settings,
    system_get_frontmost_app,
    system_get_appearance_settings,
    system_get_settings_snapshot,
    system_health,
    system_list_settings_domains,
    system_list_running_apps,
    system_open_application,
    system_permission_guide as standalone_system_permission_guide,
    system_read_preference_domain,
    system_set_appearance_mode,
    system_set_clipboard,
    system_set_dock_autohide,
    system_set_dock_show_recents,
    system_set_finder_path_bar,
    system_set_finder_status_bar,
    system_set_increase_contrast,
    system_set_reduce_motion,
    system_set_reduce_transparency,
    system_set_show_all_extensions,
    system_set_show_hidden_files,
    system_show_notification,
    system_status,
    system_settings_resource,
    system_status_resource,
)
from apple_maps_mcp.tools import (  # noqa: E402
    maps_build_maps_link,
    maps_get_directions,
    maps_health,
    maps_open_directions_in_maps,
    maps_permission_guide as standalone_maps_permission_guide,
    maps_plan_route_prompt,
    maps_search_places,
    maps_status_resource,
)

SERVER_INSTRUCTIONS = (
    "Use this server for unified Apple ecosystem access on macOS. "
    "Search here when the user wants one Apple-native entrypoint across Mail, Calendar, Reminders, Messages, Contacts, Notes, Shortcuts, Files, System, and Maps. "
    "Prefer Apple overview resources and prompts first, then use namespaced domain tools for specific actions. "
    "Route person-based communication through Contacts before Messages or Mail, confirm if multiple contacts match, and omit service_name entirely on iMessage sends. "
    "For Mail, searches require a query string such as sender, subject fragment, or '*'; if text versus email is ambiguous, ask once. "
    "For Calendar writes, confirm date, time, duration, and title before creating or updating an event. "
    "For Reminders, use due items and follow-ups, identify available lists on first use, and require due_date values with a timezone offset like 2026-03-29T23:59:00-05:00. "
    "For Notes, identify available accounts and folders on first use and use Notes for reference material rather than time-sensitive work. "
    "For Shortcuts, list available shortcuts before running one if the request is vague. "
    "Use Files before Mail, Messages, Notes, or Shortcuts when the user references a local document or attachment, and keep file mutations inside the allowed roots. "
    "Use System when clipboard state, the frontmost app, running applications, notifications, or battery state matters. "
    "Use Maps when a route, place lookup, or travel estimate affects scheduling or communication. "
    "Disambiguate as follows: due date or time goes to Reminders, reference material with no action goes to Notes, and requests involving another person usually go to Messages or Mail after Contacts resolution. "
    "Some clients defer tool schemas, so batch tool discovery on first use when needed."
)

mcp = FastMCP("Apple-Tools-MCP", instructions=SERVER_INSTRUCTIONS, json_response=True)
_ANY_URL = TypeAdapter(AnyUrl)
_SUBSCRIBED_RESOURCES: set[str] = set()


def _as_any_url(uri: str) -> AnyUrl:
    return _ANY_URL.validate_python(uri)

LOGGER = logging.getLogger("apple_agent_mcp")


class MessageInputRequest(BaseModel):
    recipient: str
    text: str
    service_name: str | None = None


class EventInputRequest(BaseModel):
    title: str
    start_iso: str
    end_iso: str
    calendar_id: str
    notes: str | None = None
    location: str | None = None
    all_day: bool = False


def _to_jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "__dict__"):
        return {
            str(key): _to_jsonable(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    return value


def _load_json_resource(resource_text: str) -> dict[str, Any]:
    try:
        payload = json.loads(resource_text)
    except json.JSONDecodeError:
        return {"ok": False, "message": "Resource returned invalid JSON."}
    return payload if isinstance(payload, dict) else {"ok": False, "message": "Resource returned a non-object payload."}


def _safe_resource_call(loader: Callable[[], str]) -> dict[str, Any]:
    try:
        return _load_json_resource(loader())
    except Exception as exc:
        return {
            "ok": False,
            "error_code": exc.__class__.__name__,
            "message": str(exc),
        }


def _coerce_int_arg(name: str, value: int | str, *, minimum: int | None = None) -> int:
    try:
        normalized = int(str(value).strip()) if isinstance(value, str) else int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if minimum is not None and normalized < minimum:
        comparator = "greater than zero" if minimum == 1 else f"at least {minimum}"
        raise ValueError(f"{name} must be {comparator}")
    return normalized


def _apple_error_response(error_code: str, message: str, suggestion: str | None = None) -> AppleErrorResponse:
    return AppleErrorResponse(error=AppleToolError(error_code=error_code, message=message, suggestion=suggestion))


def _state_path() -> Path:
    return Path(load_settings().state_file).expanduser()


def _get_preferences() -> AssistantPreferences:
    return load_preferences(_state_path())


def _save_preferences(preferences: AssistantPreferences) -> AssistantPreferences:
    return save_preferences(_state_path(), preferences)


def _history_path() -> Path:
    return _state_path().with_name("actions.json")


def _get_action_history() -> list[AssistantActionRecord]:
    return load_action_history(_history_path())


def _save_action_history(actions: list[AssistantActionRecord]) -> list[AssistantActionRecord]:
    return save_action_history(_history_path(), actions[:100])


def _record_action(
    action_type: str,
    summary: str,
    *,
    undo_supported: bool,
    undo_tool: str | None = None,
    undo_arguments: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
) -> AssistantActionRecord:
    action = AssistantActionRecord(
        action_id=str(uuid4()),
        action_type=action_type,
        created_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        summary=summary,
        undo_supported=undo_supported,
        undo_status="available" if undo_supported else "not_supported",
        undo_tool=undo_tool,
        undo_arguments=undo_arguments,
        result=result or {},
    )
    actions = _get_action_history()
    actions.insert(0, action)
    _save_action_history(actions)
    return action


def _update_action_record(updated_action: AssistantActionRecord) -> AssistantActionRecord:
    actions = _get_action_history()
    for index, action in enumerate(actions):
        if action.action_id == updated_action.action_id:
            actions[index] = updated_action
            _save_action_history(actions)
            return updated_action
    raise StateStoreError(
        "ACTION_NOT_FOUND",
        f"Assistant action '{updated_action.action_id}' was not found in history.",
        "Call apple_list_recent_actions to inspect the available action ids.",
    )


def _mail_response_ok(value: Any) -> bool:
    return not isinstance(value, MailErrorResponse)


def _pick_archive_mailbox() -> tuple[str | None, str | None]:
    response = mail_list_mailboxes()
    if not _mail_response_ok(response):
        return None, None
    exact_names = ("archive", "all archive", "archives")
    fallback: tuple[str | None, str | None] = (None, None)
    for mailbox in response.mailboxes:
        normalized = mailbox.name.strip().lower()
        if normalized in exact_names:
            return mailbox.name, mailbox.account
        if fallback == (None, None) and "archive" in normalized:
            fallback = (mailbox.name, mailbox.account)
    return fallback


def _pick_default_calendar() -> tuple[str | None, str | None]:
    response = calendar_list_calendars()
    if not getattr(response, "ok", False):
        return None, None
    preferred = []
    fallback = []
    for calendar in response.calendars:
        if calendar.writable is False:
            continue
        normalized = calendar.name.strip().lower()
        target = fallback
        if "holiday" not in normalized and "birthday" not in normalized:
            target = preferred
        target.append(calendar)
    pool = preferred or fallback
    if not pool:
        return None, None
    chosen = pool[0]
    return chosen.calendar_id, chosen.name


def _pick_default_reminder_list() -> tuple[str | None, str | None]:
    response = reminders_list_lists()
    if not getattr(response, "ok", False):
        return None, None
    preferred_names = ("general", "reminders")
    for reminder_list in response.lists:
        if reminder_list.title.strip().lower() in preferred_names:
            return reminder_list.list_id, reminder_list.title
    if not response.lists:
        return None, None
    return response.lists[0].list_id, response.lists[0].title


def _pick_default_notes_folder() -> tuple[str | None, str | None, str | None]:
    response = notes_list_folders(limit=100, offset=0)
    if not getattr(response, "ok", False):
        return None, None, None
    preferred_names = ("notes", "general")
    for folder in response.folders:
        if folder.name.strip().lower() in preferred_names:
            return folder.folder_id, folder.name, folder.account_name
    if not response.folders:
        return None, None, None
    chosen = response.folders[0]
    return chosen.folder_id, chosen.name, chosen.account_name


def _detect_preferences(base: AssistantPreferences | None = None) -> tuple[AssistantPreferences, list[str]]:
    current = base or _get_preferences()
    detected: list[str] = []
    updates: dict[str, Any] = {}

    archive_mailbox, archive_account = _pick_archive_mailbox()
    if archive_mailbox and current.default_archive_mailbox is None:
        updates["default_archive_mailbox"] = archive_mailbox
        detected.append(f"archive mailbox -> {archive_account} / {archive_mailbox}" if archive_account else f"archive mailbox -> {archive_mailbox}")
    if archive_account and current.default_archive_account is None:
        updates["default_archive_account"] = archive_account
    if archive_account and current.default_mail_account is None:
        updates["default_mail_account"] = archive_account
        detected.append(f"default mail account -> {archive_account}")

    calendar_id, calendar_name = _pick_default_calendar()
    if calendar_id and current.default_calendar_id is None:
        updates["default_calendar_id"] = calendar_id
        updates["default_calendar_name"] = calendar_name
        detected.append(f"default calendar -> {calendar_name}")

    reminder_list_id, reminder_list_name = _pick_default_reminder_list()
    if reminder_list_id and current.default_reminder_list_id is None:
        updates["default_reminder_list_id"] = reminder_list_id
        updates["default_reminder_list_name"] = reminder_list_name
        detected.append(f"default reminders list -> {reminder_list_name}")

    notes_folder_id, notes_folder_name, notes_account_name = _pick_default_notes_folder()
    if notes_folder_id and current.default_notes_folder_id is None:
        updates["default_notes_folder_id"] = notes_folder_id
        updates["default_notes_folder_name"] = notes_folder_name
        updates["default_notes_account_name"] = notes_account_name
        label = f"{notes_account_name} / {notes_folder_name}" if notes_account_name else str(notes_folder_name)
        detected.append(f"default notes folder -> {label}")

    return current.model_copy(update=updates), detected


def _pick_message_target_from_contact(contact: Any, preferences: AssistantPreferences) -> tuple[str | None, str | None]:
    contact_preference = preferences.contact_preferences.get(getattr(contact, "contact_id", ""))
    preferred_message_channel = contact_preference.preferred_message_channel if contact_preference is not None else preferences.preferred_message_channel
    preferred_message_target = contact_preference.preferred_message_target if contact_preference is not None else None
    if preferred_message_target:
        for phone in getattr(contact, "phones", []):
            if phone.value == preferred_message_target:
                return "phone", phone.value
        for email in getattr(contact, "emails", []):
            if email.value == preferred_message_target:
                return "email", email.value
    if preferred_message_channel == "email" and getattr(contact, "emails", []):
        return "email", contact.emails[0].value
    if preferred_message_channel == "phone" and getattr(contact, "phones", []):
        return "phone", contact.phones[0].value
    if getattr(contact, "phones", []):
        return "phone", contact.phones[0].value
    if getattr(contact, "emails", []):
        return "email", contact.emails[0].value
    return None, None


def _resolve_archive_target(
    preferences: AssistantPreferences,
    archive_mailbox: str | None = None,
    archive_account: str | None = None,
) -> tuple[tuple[str, str | None, AssistantPreferences], AppleErrorResponse | None]:
    target_mailbox = archive_mailbox or preferences.default_archive_mailbox
    target_account = archive_account or preferences.default_archive_account
    updated_preferences = preferences
    if not target_mailbox:
        detected_preferences, detected = _detect_preferences(preferences)
        updated_preferences = _save_preferences(detected_preferences) if detected else preferences
        target_mailbox = updated_preferences.default_archive_mailbox
        target_account = target_account or updated_preferences.default_archive_account
    if not target_mailbox:
        return (
            ("", target_account, updated_preferences),
            _apple_error_response(
                "ARCHIVE_MAILBOX_NOT_FOUND",
                "Could not determine an Archive mailbox.",
                "Set default_archive_mailbox or pass archive_mailbox explicitly.",
            ),
    )
    return (target_mailbox, target_account, updated_preferences), None


def _resolve_reminder_target(
    preferences: AssistantPreferences,
    list_id: str | None = None,
) -> tuple[tuple[str, AssistantPreferences], AppleErrorResponse | None]:
    effective_list_id = list_id or preferences.default_reminder_list_id
    updated_preferences = preferences
    if not effective_list_id:
        detected_preferences, detected = _detect_preferences(preferences)
        updated_preferences = _save_preferences(detected_preferences) if detected else preferences
        effective_list_id = updated_preferences.default_reminder_list_id
    if not effective_list_id:
        return (
            ("", updated_preferences),
            _apple_error_response(
                "DEFAULT_REMINDER_LIST_MISSING",
                "No default reminder list is configured.",
                "Call apple_detect_defaults, set default_reminder_list_id, or pass list_id explicitly.",
            ),
        )
    return (effective_list_id, updated_preferences), None


def _resolve_notes_target(
    preferences: AssistantPreferences,
    folder_id: str | None = None,
) -> tuple[tuple[str, AssistantPreferences], AppleErrorResponse | None]:
    effective_folder_id = folder_id or preferences.default_notes_folder_id
    updated_preferences = preferences
    if not effective_folder_id:
        detected_preferences, detected = _detect_preferences(preferences)
        updated_preferences = _save_preferences(detected_preferences) if detected else preferences
        effective_folder_id = updated_preferences.default_notes_folder_id
    if not effective_folder_id:
        return (
            ("", updated_preferences),
            _apple_error_response(
                "DEFAULT_NOTES_FOLDER_MISSING",
                "No default notes folder is configured.",
                "Call apple_detect_defaults, set default_notes_folder_id, or pass folder_id explicitly.",
            ),
        )
    return (effective_folder_id, updated_preferences), None


def _resolve_contact_for_communication(recipient: str) -> tuple[Any | None, AppleErrorResponse | None]:
    if _looks_like_message_address(recipient):
        return None, None
    search_result = contacts_search_contacts(query=recipient, limit=10)
    if isinstance(search_result, ContactsErrorResponse):
        return None, _apple_error_response(
            search_result.error.error_code,
            search_result.error.message,
            search_result.error.suggestion,
        )
    if search_result.count == 0:
        return None, _apple_error_response(
            "CONTACT_NOT_FOUND",
            f"No contact matched '{recipient}'.",
            "Search contacts first or provide a direct email address or phone number.",
        )
    exact_matches = [contact for contact in search_result.contacts if contact.name.strip().lower() == recipient.strip().lower()]
    if len(exact_matches) == 1:
        detail = contacts_get_contact(exact_matches[0].contact_id)
        if isinstance(detail, ContactsErrorResponse):
            return None, _apple_error_response(detail.error.error_code, detail.error.message, detail.error.suggestion)
        return detail.contact, None
    if search_result.count > 1:
        return None, _apple_error_response(
            "AMBIGUOUS_CONTACT",
            f"Multiple contacts matched '{recipient}'.",
            "Call contacts_search_contacts first, then use a specific contact.",
        )
    detail = contacts_get_contact(search_result.contacts[0].contact_id)
    if isinstance(detail, ContactsErrorResponse):
        return None, _apple_error_response(detail.error.error_code, detail.error.message, detail.error.suggestion)
    return detail.contact, None


def _build_note_html_from_mail(message: MailMessageRecord) -> str:
    lines = [
        f"<div><b>Subject:</b> {html_escape(message.subject)}</div>",
        f"<div><b>From:</b> {html_escape(message.sender)}</div>",
        f"<div><b>Received:</b> {html_escape(message.date_received)}</div>",
    ]
    if message.to:
        lines.append(f"<div><b>To:</b> {html_escape(', '.join(message.to))}</div>")
    if message.cc:
        lines.append(f"<div><b>Cc:</b> {html_escape(', '.join(message.cc))}</div>")
    lines.append("<div><br></div>")
    for line in (message.body_text or "").splitlines() or [""]:
        lines.append(f"<div>{html_escape(line)}</div>" if line else "<div><br></div>")
    return "".join(lines)


def _serialize_prompt_messages(messages: list[Any]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for item in messages:
        content = item.content.model_dump(mode="json") if hasattr(item.content, "model_dump") else item.content
        payload.append({"role": getattr(item, "role", "user"), "content": content})
    return payload


async def _notify_apple_resource_updates(ctx: Context | None, *uris: str, list_changed: bool = False) -> None:
    if ctx is None:
        return
    for uri in uris:
        await ctx.session.send_resource_updated(_as_any_url(uri))
    if list_changed:
        await ctx.session.send_resource_list_changed()


def _domain_health() -> dict[str, dict[str, Any]]:
    return {
        "mail": _to_jsonable(mail_health()),
        "calendar": _to_jsonable(calendar_health()),
        "reminders": _to_jsonable(reminders_health()),
        "messages": _to_jsonable(messages_health()),
        "contacts": _to_jsonable(contacts_health()),
        "notes": _to_jsonable(notes_health()),
        "shortcuts": _to_jsonable(shortcuts_health()),
        "files": _to_jsonable(files_health()),
        "system": _to_jsonable(system_health()),
        "maps": _to_jsonable(maps_health()),
    }


def _mailboxes_resource() -> str:
    return mailboxes_resource_tool(AppleMailBridge())


def _filter_text(values: list[str], query: str | None = None, limit: int = 25) -> list[str]:
    if query:
        needle = query.strip().lower()
        values = [value for value in values if needle in value.lower()]
    deduped: list[str] = []
    for value in values:
        if value not in deduped:
            deduped.append(value)
    return deduped[:limit]


def _permission_guide(domain: str) -> PermissionGuideResponse:
    normalized = domain.strip().lower()
    guides = {
        "calendar": PermissionGuideResponse(
            domain="calendar",
            can_prompt_in_app=True,
            requires_manual_system_settings=False,
            steps=[
                "Call a Calendar read or write tool from the MCP server.",
                "Approve the macOS Calendar access prompt when it appears.",
                "If access was denied before, re-enable it in System Settings > Privacy & Security > Calendars.",
            ],
            notes=["Calendar access can usually trigger a system prompt on first use."],
        ),
        "reminders": PermissionGuideResponse(
            domain="reminders",
            can_prompt_in_app=True,
            requires_manual_system_settings=False,
            steps=[
                "Call a Reminders read or write tool from the MCP server.",
                "Approve the macOS Reminders access prompt when it appears.",
                "If access was denied before, re-enable it in System Settings > Privacy & Security > Reminders.",
            ],
            notes=["Reminders access can usually trigger a system prompt on first use."],
        ),
        "messages": PermissionGuideResponse(
            domain="messages",
            can_prompt_in_app=True,
            requires_manual_system_settings=True,
            steps=[
                "Call a Messages send tool to trigger the macOS Automation prompt for Messages.app.",
                "Approve Automation access when prompted.",
                "Grant Full Disk Access manually in System Settings > Privacy & Security > Full Disk Access for history access to chat.db.",
            ],
            notes=["Messages send access and history access are separate permissions.", "Full Disk Access cannot be requested programmatically."],
        ),
        "contacts": PermissionGuideResponse(
            domain="contacts",
            can_prompt_in_app=True,
            requires_manual_system_settings=False,
            steps=[
                "Call a Contacts read tool from the MCP server.",
                "Approve the macOS Contacts access prompt when it appears.",
                "If access was denied before, re-enable it in System Settings > Privacy & Security > Contacts.",
            ],
            notes=["Contacts lookups can resolve a recipient before sending through Apple Messages."],
        ),
        "mail": PermissionGuideResponse(
            domain="mail",
            can_prompt_in_app=True,
            requires_manual_system_settings=False,
            steps=[
                "Call a Mail tool that uses Apple Mail automation.",
                "Approve the macOS Automation prompt for Mail if it appears.",
                "If access was denied before, re-enable it in System Settings > Privacy & Security > Automation.",
            ],
            notes=["Mail access is typically driven by Apple Events automation prompts."],
        ),
        "notes": PermissionGuideResponse(
            domain="notes",
            can_prompt_in_app=True,
            requires_manual_system_settings=False,
            steps=[
                "Call a Notes tool that uses Notes.app automation.",
                "Approve the macOS Automation prompt for Notes if it appears.",
                "If access was denied before, re-enable it in System Settings > Privacy & Security > Automation.",
            ],
            notes=["Notes access is primarily automation-based in this repo."],
        ),
        "shortcuts": PermissionGuideResponse(
            domain="shortcuts",
            can_prompt_in_app=False,
            requires_manual_system_settings=False,
            steps=[
                "Ensure the `shortcuts` CLI is available.",
                "Run a Shortcuts list or run tool.",
            ],
            notes=["Shortcuts typically does not require a separate privacy prompt for basic CLI operations."],
        ),
        "files": PermissionGuideResponse(
            domain="files",
            can_prompt_in_app=False,
            requires_manual_system_settings=False,
            steps=[
                "Use files_list_allowed_roots to inspect the current file access scope.",
                "Restart the MCP with APPLE_FILES_MCP_ALLOWED_ROOTS if you need different root folders.",
                "Use APPLE_FILES_MCP_SAFETY_MODE=safe_manage or full_access only when file mutations are necessary.",
            ],
            notes=["Files access is controlled by environment-scoped roots rather than a macOS privacy prompt."],
        ),
        "system": PermissionGuideResponse(
            domain="system",
            can_prompt_in_app=True,
            requires_manual_system_settings=False,
            steps=standalone_system_permission_guide()["steps"],
            notes=standalone_system_permission_guide().get("notes", []),
        ),
        "maps": PermissionGuideResponse(
            domain="maps",
            can_prompt_in_app=False,
            requires_manual_system_settings=False,
            steps=standalone_maps_permission_guide()["steps"],
            notes=standalone_maps_permission_guide().get("notes", []),
        ),
        "all": PermissionGuideResponse(
            domain="all",
            can_prompt_in_app=True,
            requires_manual_system_settings=True,
            steps=[
                "Use the domain-specific guide for the app you want to authorize.",
                "Grant automation prompts when they appear.",
                "Grant Contacts access if you want to resolve recipients by contact name before messaging.",
                "Grant Full Disk Access manually for Apple Messages history access.",
                "Keep Apple Files roots scoped to the folders the assistant should use.",
            ],
            notes=["Some Apple permissions can be prompted in-app.", "Full Disk Access must be granted manually in System Settings."],
        ),
    }
    return guides.get(normalized, guides["all"])


def mail_health() -> MailHealthResponse:
    return _mail_health()


def mail_list_mailboxes(account: str | None = None) -> MailboxListResponse | MailErrorResponse:
    return _mail_list_mailboxes(account=account)


def mail_search_messages(
    query: str,
    mailbox: str | None = None,
    unread_only: bool = False,
    limit: int | str = 10,
) -> MailMessageSearchResponse | MailErrorResponse:
    return _mail_search_messages(
        query=query,
        mailbox=mailbox,
        unread_only=unread_only,
        limit=_coerce_int_arg("limit", limit, minimum=1),
    )


def mail_get_message(message_id: str) -> MailMessageRecord | MailErrorResponse:
    return _mail_get_message(message_id=message_id)


def mail_get_thread(message_id: str, limit: int | str = 25) -> MailThreadRecord | MailErrorResponse:
    return _mail_get_thread(message_id=message_id, limit=_coerce_int_arg("limit", limit, minimum=1))


def mail_compose_draft(
    to: list[str],
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    subject: str = "",
    body: str = "",
    attachments: list[str] | None = None,
    from_account: str | None = None,
) -> MailDraftRecord | MailErrorResponse:
    return _mail_compose_draft(
        to=to,
        cc=cc,
        bcc=bcc,
        subject=subject,
        body=body,
        attachments=attachments,
        from_account=from_account,
    )


def mail_send_message(
    to: list[str],
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    subject: str = "",
    body: str = "",
    attachments: list[str] | None = None,
    from_account: str | None = None,
) -> MailSendRecord | MailErrorResponse:
    return _mail_send_message(
        to=to,
        cc=cc,
        bcc=bcc,
        subject=subject,
        body=body,
        attachments=attachments,
        from_account=from_account,
    )


def mail_reply_message(
    message_id: str,
    body: str,
    reply_all: bool = False,
    from_account: str | None = None,
) -> MailReplyRecord | MailErrorResponse:
    return _mail_reply_message(
        message_id=message_id,
        body=body,
        reply_all=reply_all,
        from_account=from_account,
    )


def mail_forward_message(
    message_id: str,
    to: list[str],
    body: str = "",
    from_account: str | None = None,
) -> MailForwardRecord | MailErrorResponse:
    return _mail_forward_message(
        message_id, to=to, body=body, from_account=from_account
    )


def mail_mark_message(
    message_id: str,
    is_read: bool,
) -> MailMarkRecord | MailErrorResponse:
    return _mail_mark_message(message_id, is_read=is_read)


def mail_move_message(
    message_id: str,
    target_mailbox: str,
    target_account: str | None = None,
) -> MailMoveRecord | MailErrorResponse:
    return _mail_move_message(message_id, target_mailbox=target_mailbox, target_account=target_account)


def mail_delete_message(message_id: str) -> MailDeleteRecord | MailErrorResponse:
    return _mail_delete_message(message_id)


def mail_reply_latest_in_thread(
    message_id: str,
    body: str,
    reply_all: bool = False,
    from_account: str | None = None,
    limit: int | str = 25,
) -> MailReplyRecord | MailErrorResponse:
    return _mail_reply_latest_in_thread(
        message_id=message_id,
        body=body,
        reply_all=reply_all,
        from_account=from_account,
        limit=_coerce_int_arg("limit", limit, minimum=1),
    )


def mail_archive_thread(
    message_id: str,
    archive_mailbox: str = "Archive",
    archive_account: str | None = None,
    limit: int | str = 25,
) -> MailThreadMutationRecord | MailErrorResponse:
    return _mail_archive_thread(
        message_id=message_id,
        archive_mailbox=archive_mailbox,
        archive_account=archive_account,
        limit=_coerce_int_arg("limit", limit, minimum=1),
    )


def contacts_create_contact(
    first_name: str,
    last_name: str = "",
    organization: str = "",
    phones: list[ContactMethod] | None = None,
    emails: list[ContactMethod] | None = None,
    note: str = "",
) -> CreateContactResponse | ContactsErrorResponse:
    return _contacts_create_contact(
        first_name=first_name,
        last_name=last_name,
        organization=organization,
        phones=phones,
        emails=emails,
        note=note,
    )


def contacts_update_contact(
    contact_id: str,
    first_name: str = "",
    last_name: str = "",
    organization: str = "",
    phones: list[ContactMethod] | None = None,
    emails: list[ContactMethod] | None = None,
    note: str = "",
) -> ContactResponse | ContactsErrorResponse:
    return _contacts_update_contact(
        contact_id=contact_id,
        first_name=first_name,
        last_name=last_name,
        organization=organization,
        phones=phones,
        emails=emails,
        note=note,
    )


def contacts_delete_contact(contact_id: str) -> DeleteContactResponse | ContactsErrorResponse:
    return _contacts_delete_contact(contact_id)


def notes_append_to_note(
    note_id: str,
    body: str,
) -> NotesNoteResponse | NotesErrorResponse:
    return _notes_append_to_note(note_id, body_text=body)


def messages_send_attachment(
    recipient: str,
    file_path: str,
    text: str | None = None,
) -> SendResponse | MessagesErrorResponse:
    return _messages_send_attachment(recipient, file_path=file_path, text=text)


def reminders_create_list(title: str) -> ReminderListMutationResponse | RemindersErrorResponse:
    return _reminders_create_list(title=title)


def reminders_delete_list(list_id: str) -> DeleteReminderListResponse | RemindersErrorResponse:
    return _reminders_delete_list(list_id=list_id)


@mcp.tool(
    title="Apple Get Preferences",
    description="Read the persisted Apple-Tools assistant defaults and routing preferences.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def apple_get_preferences() -> PreferencesResponse | AppleErrorResponse:
    try:
        return PreferencesResponse(preferences=_get_preferences())
    except StateStoreError as exc:
        return _apple_error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Apple Detect Defaults",
    description="Detect sensible default mail, calendar, reminders, and notes targets, then persist them if missing.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=False),
    structured_output=True,
)
def apple_detect_defaults() -> PreferencesDetectResponse | AppleErrorResponse:
    try:
        detected_preferences, detected = _detect_preferences()
        stored = _save_preferences(detected_preferences)
        return PreferencesDetectResponse(preferences=stored, detected=detected, count=len(detected))
    except StateStoreError as exc:
        return _apple_error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Apple Update Preferences",
    description="Persist assistant defaults such as default lists, folders, calendars, archive mailboxes, and preferred communication routing.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def apple_update_preferences(
    default_mail_account: str | None = None,
    default_archive_mailbox: str | None = None,
    default_archive_account: str | None = None,
    default_calendar_id: str | None = None,
    default_calendar_name: str | None = None,
    default_reminder_list_id: str | None = None,
    default_reminder_list_name: str | None = None,
    default_notes_folder_id: str | None = None,
    default_notes_folder_name: str | None = None,
    default_notes_account_name: str | None = None,
    preferred_communication_channel: str | None = None,
    preferred_message_channel: str | None = None,
) -> PreferencesResponse | AppleErrorResponse:
    try:
        current = _get_preferences()
        updates = {
            key: value
            for key, value in {
                "default_mail_account": default_mail_account,
                "default_archive_mailbox": default_archive_mailbox,
                "default_archive_account": default_archive_account,
                "default_calendar_id": default_calendar_id,
                "default_calendar_name": default_calendar_name,
                "default_reminder_list_id": default_reminder_list_id,
                "default_reminder_list_name": default_reminder_list_name,
                "default_notes_folder_id": default_notes_folder_id,
                "default_notes_folder_name": default_notes_folder_name,
                "default_notes_account_name": default_notes_account_name,
                "preferred_communication_channel": preferred_communication_channel,
                "preferred_message_channel": preferred_message_channel,
            }.items()
            if value is not None
        }
        updated = current.model_copy(update=updates)
        stored = _save_preferences(AssistantPreferences.model_validate(updated.model_dump()))
        return PreferencesResponse(preferences=stored)
    except StateStoreError as exc:
        return _apple_error_response(exc.error_code, exc.message, exc.suggestion)
    except Exception as exc:
        return _apple_error_response("INVALID_INPUT", str(exc), "Check the preference values and retry.")


@mcp.tool(
    title="Apple Update Contact Preferences",
    description="Persist preferred communication routing for a specific contact so Apple-Tools can choose the right channel and target for that person.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def apple_update_contact_preferences(
    contact_id: str,
    preferred_communication_channel: str | None = None,
    preferred_message_channel: str | None = None,
    preferred_mail_address: str | None = None,
    preferred_message_target: str | None = None,
    clear_existing: bool = False,
) -> PreferencesResponse | AppleErrorResponse:
    try:
        current = _get_preferences()
        contact_preferences = dict(current.contact_preferences)
        existing = ContactRoutingPreference() if clear_existing else contact_preferences.get(contact_id, ContactRoutingPreference())
        updates = {
            key: value
            for key, value in {
                "preferred_communication_channel": preferred_communication_channel,
                "preferred_message_channel": preferred_message_channel,
                "preferred_mail_address": preferred_mail_address if preferred_mail_address != "" else None,
                "preferred_message_target": preferred_message_target if preferred_message_target != "" else None,
            }.items()
            if value is not None
        }
        contact_preferences[contact_id] = existing.model_copy(update=updates)
        stored = _save_preferences(
            AssistantPreferences.model_validate(current.model_copy(update={"contact_preferences": contact_preferences}).model_dump())
        )
        return PreferencesResponse(preferences=stored)
    except StateStoreError as exc:
        return _apple_error_response(exc.error_code, exc.message, exc.suggestion)
    except Exception as exc:
        return _apple_error_response("INVALID_INPUT", str(exc), "Check the contact preference values and retry.")


def _communication_plan_for(
    recipient: str,
    preferred_channel: str | None = None,
) -> CommunicationPlanResponse | AppleErrorResponse:
    preferences = _get_preferences()
    contact, contact_error = _resolve_contact_for_communication(recipient)
    if contact_error is not None:
        return contact_error

    channels_available: list[str] = []
    recommended_channel = preferred_channel or preferences.preferred_communication_channel
    recommended_target: str | None = None
    rationale = ""
    resolved_contact_id: str | None = None
    resolved_contact_name: str | None = None

    if contact is None:
        if "@" in recipient:
            channels_available = ["mail"]
            recommended_channel = "mail" if recommended_channel == "auto" else recommended_channel
            recommended_target = recipient
            rationale = "Direct email address provided."
        else:
            channels_available = ["messages"]
            recommended_channel = "messages" if recommended_channel == "auto" else recommended_channel
            recommended_target = recipient
            rationale = "Direct messaging address provided."
    else:
        resolved_contact_id = contact.contact_id
        resolved_contact_name = contact.name
        contact_preference = preferences.contact_preferences.get(contact.contact_id)
        if preferred_channel is None and contact_preference is not None:
            recommended_channel = contact_preference.preferred_communication_channel
        if contact.phones or contact.emails:
            if contact.phones or contact.emails:
                channels_available.append("messages")
            if contact.emails:
                channels_available.append("mail")
        if not channels_available:
            return _apple_error_response(
                "NO_CONTACT_METHOD",
                f"Contact '{contact.name}' does not have a usable phone number or email address.",
                "Update the contact or choose another recipient.",
            )
        if recommended_channel == "auto":
            recommended_channel = "messages" if "messages" in channels_available else "mail"
        if recommended_channel == "messages":
            _, recommended_target = _pick_message_target_from_contact(contact, preferences)
            if recommended_target is None:
                return _apple_error_response(
                    "NO_MESSAGE_TARGET",
                    f"Contact '{contact.name}' does not have a message-capable address.",
                    "Choose mail instead or update the contact.",
                )
            rationale = "Messages is preferred based on contact methods and assistant preferences."
        elif recommended_channel == "mail":
            if not contact.emails:
                return _apple_error_response(
                    "NO_EMAIL_ADDRESS",
                    f"Contact '{contact.name}' does not have an email address.",
                    "Choose Messages instead or update the contact.",
                )
            preferred_mail_address = contact_preference.preferred_mail_address if contact_preference is not None else None
            if preferred_mail_address and any(email.value == preferred_mail_address for email in contact.emails):
                recommended_target = preferred_mail_address
            else:
                recommended_target = contact.emails[0].value
            rationale = "Mail is preferred based on assistant preferences or explicit routing."
        else:
            return _apple_error_response(
                "INVALID_INPUT",
                f"Unsupported channel '{recommended_channel}'.",
                "Use 'auto', 'messages', or 'mail'.",
            )

    if recommended_channel not in channels_available:
        return _apple_error_response(
            "CHANNEL_UNAVAILABLE",
            f"Channel '{recommended_channel}' is not available for '{recipient}'.",
            "Choose one of the available channels or update the contact.",
        )
    if recommended_channel not in {"messages", "mail"} or recommended_target is None:
        return _apple_error_response(
            "NO_ROUTE_AVAILABLE",
            f"Could not determine how to contact '{recipient}'.",
            "Provide an explicit channel or update assistant preferences.",
        )

    return CommunicationPlanResponse(
        recipient_query=recipient,
        resolved_contact_id=resolved_contact_id,
        resolved_contact_name=resolved_contact_name,
        channels_available=channels_available,
        recommended_channel=recommended_channel,
        recommended_target=recommended_target,
        rationale=rationale,
    )


@mcp.tool(
    title="Apple Prepare Communication",
    description="Resolve a recipient through Contacts, evaluate available channels, and return the recommended mail or messages target before sending.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def apple_prepare_communication(
    recipient: str,
    preferred_channel: str | None = None,
) -> CommunicationPlanResponse | AppleErrorResponse:
    try:
        return _communication_plan_for(recipient, preferred_channel=preferred_channel)
    except StateStoreError as exc:
        return _apple_error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Apple Preview Communication",
    description="Preview how Apple-Tools will route a communication before sending it through Messages or Mail.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def apple_preview_communication(
    recipient: str,
    message: str,
    preferred_channel: str | None = None,
    subject: str = "",
    attachments: list[str] | None = None,
    from_account: str | None = None,
) -> ActionPreviewResponse | AppleErrorResponse:
    try:
        plan = _communication_plan_for(recipient, preferred_channel=preferred_channel)
        if isinstance(plan, AppleErrorResponse):
            return plan
        preferences = _get_preferences()
        warnings: list[str] = []
        if plan.recommended_channel == "messages" and attachments and len(attachments) != 1:
            return _apple_error_response(
                "INVALID_INPUT",
                "Messages supports exactly one attachment per send operation in this assistant workflow.",
                "Send one attachment at a time, or route through Mail for multiple attachments.",
            )
        if plan.recommended_channel == "mail" and not subject.strip():
            warnings.append("Mail preview has an empty subject.")
        summary = (
            f"Send a {plan.recommended_channel} communication to {plan.recommended_target}"
            if plan.recommended_channel == "messages"
            else f"Send an email to {plan.recommended_target} from {from_account or preferences.default_mail_account or 'the default Mail account'}"
        )
        return ActionPreviewResponse(
            action_type="send_communication",
            summary=summary,
            execution_tool="apple_send_communication",
            execution_arguments={
                "recipient": recipient,
                "message": message,
                "preferred_channel": preferred_channel,
                "subject": subject,
                "attachments": attachments,
                "from_account": from_account,
            },
            undo_supported=False,
            warnings=warnings,
        )
    except StateStoreError as exc:
        return _apple_error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Apple Preview Archive Message",
    description="Preview how Apple-Tools will archive a Mail message before moving it.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def apple_preview_archive_message(
    message_id: str,
    archive_mailbox: str | None = None,
    archive_account: str | None = None,
) -> ActionPreviewResponse | AppleErrorResponse:
    try:
        message = mail_get_message(message_id)
        if isinstance(message, MailErrorResponse):
            return _apple_error_response(message.error_code, message.message, None)
        preferences = _get_preferences()
        resolved, error = _resolve_archive_target(preferences, archive_mailbox=archive_mailbox, archive_account=archive_account)
        if error is not None:
            return error
        target_mailbox, target_account, _ = resolved
        account_label = f"{target_account} / " if target_account else ""
        return ActionPreviewResponse(
            action_type="archive_message",
            summary=f"Move '{message.subject or message.message_id}' from {message.mailbox} to {account_label}{target_mailbox}.",
            execution_tool="apple_archive_message",
            execution_arguments={
                "message_id": message_id,
                "archive_mailbox": archive_mailbox,
                "archive_account": archive_account,
            },
            undo_supported=True,
        )
    except StateStoreError as exc:
        return _apple_error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Apple Preview Create Reminder With Defaults",
    description="Preview how Apple-Tools will create a reminder with the configured default reminder list.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def apple_preview_create_reminder_with_defaults(
    title: str,
    due_date: str | None = None,
    notes: str | None = None,
    list_id: str | None = None,
    priority: int | str = 0,
) -> ActionPreviewResponse | AppleErrorResponse:
    try:
        preferences = _get_preferences()
        resolved, error = _resolve_reminder_target(preferences, list_id=list_id)
        if error is not None:
            return error
        effective_list_id, updated_preferences = resolved
        target_label = updated_preferences.default_reminder_list_name or effective_list_id
        warnings = [] if due_date else ["Reminder preview has no due date."]
        return ActionPreviewResponse(
            action_type="create_reminder",
            summary=f"Create reminder '{title}' in {target_label}.",
            execution_tool="apple_create_reminder_with_defaults",
            execution_arguments={
                "title": title,
                "due_date": due_date,
                "notes": notes,
                "list_id": list_id,
                "priority": priority,
            },
            undo_supported=True,
            warnings=warnings,
        )
    except StateStoreError as exc:
        return _apple_error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Apple Preview Create Note With Defaults",
    description="Preview how Apple-Tools will create a note with the configured default notes folder.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def apple_preview_create_note_with_defaults(
    title: str,
    body_text: str | None = None,
    body_html: str | None = None,
    folder_id: str | None = None,
    tags: list[str] | None = None,
) -> ActionPreviewResponse | AppleErrorResponse:
    try:
        preferences = _get_preferences()
        resolved, error = _resolve_notes_target(preferences, folder_id=folder_id)
        if error is not None:
            return error
        effective_folder_id, updated_preferences = resolved
        folder_label = updated_preferences.default_notes_folder_name or effective_folder_id
        account_label = updated_preferences.default_notes_account_name
        destination = f"{account_label} / {folder_label}" if account_label else folder_label
        warnings = [] if (body_text or body_html) else ["Note preview has an empty body."]
        return ActionPreviewResponse(
            action_type="create_note",
            summary=f"Create note '{title}' in {destination}.",
            execution_tool="apple_create_note_with_defaults",
            execution_arguments={
                "title": title,
                "body_text": body_text,
                "body_html": body_html,
                "folder_id": folder_id,
                "tags": tags,
            },
            undo_supported=True,
            warnings=warnings,
        )
    except StateStoreError as exc:
        return _apple_error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Apple Preview Follow-Up From Mail",
    description="Preview how Apple-Tools will turn an email into a reminder and note before creating either item.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def apple_preview_follow_up_from_mail(
    message_id: str,
    due_date: str | None = None,
    reminder_title: str | None = None,
    note_title: str | None = None,
    create_reminder: bool = True,
    create_note: bool = True,
) -> ActionPreviewResponse | AppleErrorResponse:
    try:
        message = mail_get_message(message_id)
        if isinstance(message, MailErrorResponse):
            return _apple_error_response(message.error_code, message.message, None)
        warnings: list[str] = []
        summary_parts: list[str] = [f"Capture follow-up from '{message.subject or message.message_id}'."]
        preferences = _get_preferences()
        if create_reminder:
            reminder_resolved, reminder_error = _resolve_reminder_target(preferences)
            if reminder_error is not None:
                return reminder_error
            _, updated_preferences = reminder_resolved
            reminder_target = updated_preferences.default_reminder_list_name or updated_preferences.default_reminder_list_id
            summary_parts.append(
                f"Create reminder '{reminder_title or f'Follow up: {message.subject or message.sender}'}' in {reminder_target}."
            )
            if not due_date:
                warnings.append("Follow-up reminder preview has no due date.")
        if create_note:
            note_resolved, note_error = _resolve_notes_target(preferences)
            if note_error is not None:
                return note_error
            _, updated_preferences = note_resolved
            note_target = updated_preferences.default_notes_folder_name or updated_preferences.default_notes_folder_id
            summary_parts.append(
                f"Create note '{note_title or f'Mail: {message.subject or message.sender}'}' in {note_target}."
            )
        return ActionPreviewResponse(
            action_type="capture_follow_up_from_mail",
            summary=" ".join(summary_parts),
            execution_tool="apple_capture_follow_up_from_mail",
            execution_arguments={
                "message_id": message_id,
                "due_date": due_date,
                "reminder_title": reminder_title,
                "note_title": note_title,
                "create_reminder": create_reminder,
                "create_note": create_note,
            },
            undo_supported=False,
            warnings=warnings,
        )
    except StateStoreError as exc:
        return _apple_error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Apple Send Communication",
    description="Send a communication through Messages or Mail using Contacts resolution and assistant defaults.",
    annotations=ToolAnnotations(destructiveHint=True, idempotentHint=False, openWorldHint=True),
    structured_output=True,
)
def apple_send_communication(
    recipient: str,
    message: str,
    preferred_channel: str | None = None,
    subject: str = "",
    attachments: list[str] | None = None,
    from_account: str | None = None,
) -> CommunicationActionResponse | AppleErrorResponse:
    try:
        plan = _communication_plan_for(recipient, preferred_channel=preferred_channel)
        if isinstance(plan, AppleErrorResponse):
            return plan
        preferences = _get_preferences()
        if plan.recommended_channel == "messages":
            if attachments:
                if len(attachments) != 1:
                    return _apple_error_response(
                        "INVALID_INPUT",
                        "Messages supports exactly one attachment per send operation in this assistant workflow.",
                        "Send one attachment at a time, or route through Mail for multiple attachments.",
                    )
                result = messages_send_attachment(plan.recommended_target, attachments[0], text=message)
            else:
                result = messages_send_message(recipient=plan.recommended_target, text=message)
            if isinstance(result, MessagesErrorResponse):
                return _apple_error_response(result.error.error_code, result.error.message, result.error.suggestion)
            action = _record_action(
                "send_communication",
                f"Sent a Messages communication to {plan.recommended_target}.",
                undo_supported=False,
                result={"channel": "messages", "target": plan.recommended_target, "payload": _to_jsonable(result)},
            )
            return CommunicationActionResponse(channel="messages", target=plan.recommended_target, action_id=action.action_id, result=_to_jsonable(result))

        effective_from_account = from_account or preferences.default_mail_account
        result = mail_send_message(
            to=[plan.recommended_target],
            subject=subject,
            body=message,
            attachments=attachments,
            from_account=effective_from_account,
        )
        if isinstance(result, MailErrorResponse):
            return _apple_error_response(result.error_code, result.message, None)
        action = _record_action(
            "send_communication",
            f"Sent an email to {plan.recommended_target}.",
            undo_supported=False,
            result={"channel": "mail", "target": plan.recommended_target, "payload": _to_jsonable(result)},
        )
        return CommunicationActionResponse(channel="mail", target=plan.recommended_target, action_id=action.action_id, result=_to_jsonable(result))
    except StateStoreError as exc:
        return _apple_error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Apple Archive Message",
    description="Move a message to the preferred archive mailbox, or auto-detect an archive mailbox if no preference exists yet.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def apple_archive_message(
    message_id: str,
    archive_mailbox: str | None = None,
    archive_account: str | None = None,
) -> MailMoveRecord | AppleErrorResponse:
    try:
        preferences = _get_preferences()
        message = mail_get_message(message_id)
        if isinstance(message, MailErrorResponse):
            return _apple_error_response(message.error_code, message.message, None)
        resolved, error = _resolve_archive_target(preferences, archive_mailbox=archive_mailbox, archive_account=archive_account)
        if error is not None:
            return error
        target_mailbox, target_account, _ = resolved
        result = mail_move_message(message_id=message_id, target_mailbox=target_mailbox, target_account=target_account)
        if isinstance(result, MailErrorResponse):
            return _apple_error_response(result.error_code, result.message, None)
        _record_action(
            "archive_message",
            f"Moved '{message.subject or message.message_id}' from {message.mailbox} to {target_mailbox}.",
            undo_supported=True,
            undo_tool="mail_move_message",
            undo_arguments={
                "message_id": message_id,
                "target_mailbox": message.mailbox,
                "target_account": message.account,
            },
            result=_to_jsonable(result),
        )
        return result
    except StateStoreError as exc:
        return _apple_error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Apple List Recent Actions",
    description="List recent assistant actions recorded by Apple-Tools for audit and undo workflows.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def apple_list_recent_actions(limit: int | str = 10) -> ActionHistoryResponse | AppleErrorResponse:
    try:
        bounded_limit = _coerce_int_arg("limit", limit, minimum=1)
        actions = _get_action_history()[:bounded_limit]
        return ActionHistoryResponse(actions=actions, count=len(actions))
    except StateStoreError as exc:
        return _apple_error_response(exc.error_code, exc.message, exc.suggestion)
    except ValueError as exc:
        return _apple_error_response("INVALID_INPUT", str(exc), "Provide a positive integer limit.")


@mcp.tool(
    title="Apple Undo Action",
    description="Undo a recent Apple-Tools action when the underlying standalone MCPs support a reliable reversal.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def apple_undo_action(action_id: str) -> ActionUndoResponse | AppleErrorResponse:
    try:
        actions = _get_action_history()
        action = next((item for item in actions if item.action_id == action_id), None)
        if action is None:
            return _apple_error_response(
                "ACTION_NOT_FOUND",
                f"Assistant action '{action_id}' was not found.",
                "Call apple_list_recent_actions to inspect the available action ids.",
            )
        if not action.undo_supported or not action.undo_tool or action.undo_arguments is None:
            return _apple_error_response(
                "UNDO_NOT_SUPPORTED",
                f"Action '{action_id}' cannot be undone reliably.",
                "Use apple_list_recent_actions to find an undoable action.",
            )
        if action.undo_status == "undone":
            return _apple_error_response(
                "ACTION_ALREADY_UNDONE",
                f"Action '{action_id}' was already undone.",
                "Pick a different action id.",
            )

        if action.undo_tool == "mail_move_message":
            undo_result = mail_move_message(**action.undo_arguments)
            if isinstance(undo_result, MailErrorResponse):
                updated = action.model_copy(update={"undo_status": "failed"})
                _update_action_record(updated)
                return _apple_error_response(undo_result.error_code, undo_result.message, None)
        elif action.undo_tool == "reminders_delete_reminder":
            undo_result = reminders_delete_reminder(**action.undo_arguments)
            if isinstance(undo_result, RemindersErrorResponse):
                updated = action.model_copy(update={"undo_status": "failed"})
                _update_action_record(updated)
                return _apple_error_response(undo_result.error.error_code, undo_result.error.message, undo_result.error.suggestion)
        elif action.undo_tool == "notes_delete_note":
            undo_result = notes_delete_note(**action.undo_arguments)
            if isinstance(undo_result, NotesErrorResponse):
                updated = action.model_copy(update={"undo_status": "failed"})
                _update_action_record(updated)
                return _apple_error_response(undo_result.error.error_code, undo_result.error.message, undo_result.error.suggestion)
        else:
            return _apple_error_response(
                "UNDO_NOT_SUPPORTED",
                f"Undo tool '{action.undo_tool}' is not supported.",
                "Use apple_list_recent_actions to inspect the action history.",
            )

        updated = action.model_copy(update={"undo_status": "undone"})
        _update_action_record(updated)
        return ActionUndoResponse(action=updated, undo_result=_to_jsonable(undo_result))
    except StateStoreError as exc:
        return _apple_error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Apple Create Reminder With Defaults",
    description="Create a reminder using the configured default reminder list when list_id is omitted.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def apple_create_reminder_with_defaults(
    title: str,
    due_date: str | None = None,
    notes: str | None = None,
    list_id: str | None = None,
    priority: int | str = 0,
) -> RemindersReminderResponse | RemindersErrorResponse | AppleErrorResponse:
    try:
        preferences = _get_preferences()
        resolved, error = _resolve_reminder_target(preferences, list_id=list_id)
        if error is not None:
            return error
        effective_list_id, _ = resolved
        result = reminders_create_reminder(title=title, list_id=effective_list_id, due_date=due_date, notes=notes, priority=priority)
        if not isinstance(result, RemindersErrorResponse):
            result_payload = _to_jsonable(result)
            reminder_payload = result_payload.get("reminder", {}) if isinstance(result_payload, dict) else {}
            reminder_id = reminder_payload.get("reminder_id")
            _record_action(
                "create_reminder",
                f"Created reminder '{reminder_payload.get('title', title)}'.",
                undo_supported=bool(reminder_id),
                undo_tool="reminders_delete_reminder" if reminder_id else None,
                undo_arguments={"reminder_id": reminder_id} if reminder_id else None,
                result=result_payload,
            )
        return result
    except StateStoreError as exc:
        return _apple_error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Apple Create Note With Defaults",
    description="Create a note using the configured default notes folder when folder_id is omitted.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def apple_create_note_with_defaults(
    title: str,
    body_text: str | None = None,
    body_html: str | None = None,
    folder_id: str | None = None,
    tags: list[str] | None = None,
) -> NotesNoteResponse | NotesErrorResponse | AppleErrorResponse:
    try:
        preferences = _get_preferences()
        resolved, error = _resolve_notes_target(preferences, folder_id=folder_id)
        if error is not None:
            return error
        effective_folder_id, _ = resolved
        if body_html is None and body_text is not None:
            lines = body_text.splitlines() or [body_text]
            body_html = "".join(f"<div>{html_escape(line)}</div>" if line else "<div><br></div>" for line in lines)
        result = notes_create_note(title=title, folder_id=effective_folder_id, body_html=body_html, tags=tags)
        if not isinstance(result, NotesErrorResponse):
            result_payload = _to_jsonable(result)
            note_payload = result_payload.get("note", {}) if isinstance(result_payload, dict) else {}
            note_id = note_payload.get("note_id")
            _record_action(
                "create_note",
                f"Created note '{note_payload.get('title', title)}'.",
                undo_supported=bool(note_id),
                undo_tool="notes_delete_note" if note_id else None,
                undo_arguments={"note_id": note_id} if note_id else None,
                result=result_payload,
            )
        return result
    except StateStoreError as exc:
        return _apple_error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Apple Capture Follow-Up From Mail",
    description="Turn an email into a reminder and an archival note using assistant defaults for the destination list and notes folder.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def apple_capture_follow_up_from_mail(
    message_id: str,
    due_date: str | None = None,
    reminder_title: str | None = None,
    note_title: str | None = None,
    create_reminder: bool = True,
    create_note: bool = True,
) -> MailFollowupResponse | AppleErrorResponse:
    try:
        message = mail_get_message(message_id)
        if isinstance(message, MailErrorResponse):
            return _apple_error_response(message.error_code, message.message, None)

        reminder_payload: dict[str, Any] | None = None
        note_payload: dict[str, Any] | None = None
        warnings: list[str] = []

        if create_reminder:
            resolved_reminder_title = reminder_title or f"Follow up: {message.subject or message.sender}"
            reminder_result = apple_create_reminder_with_defaults(
                title=resolved_reminder_title,
                due_date=due_date,
                notes=f"From: {message.sender}\nSubject: {message.subject}\nReceived: {message.date_received}",
            )
            if isinstance(reminder_result, AppleErrorResponse):
                warnings.append(reminder_result.error.message)
            elif getattr(reminder_result, "ok", True) is False:
                warnings.append(getattr(reminder_result.error, "message", "Reminder creation failed."))
            else:
                reminder_payload = _to_jsonable(reminder_result)

        if create_note:
            resolved_note_title = note_title or f"Mail: {message.subject or message.sender}"
            note_result = apple_create_note_with_defaults(
                title=resolved_note_title,
                body_html=_build_note_html_from_mail(message),
            )
            if isinstance(note_result, AppleErrorResponse):
                warnings.append(note_result.error.message)
            elif getattr(note_result, "ok", True) is False:
                warnings.append(getattr(note_result.error, "message", "Note creation failed."))
            else:
                note_payload = _to_jsonable(note_result)

        return MailFollowupResponse(
            message_id=message_id,
            reminder=reminder_payload,
            note=note_payload,
            warnings=warnings,
        )
    except StateStoreError as exc:
        return _apple_error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Apple Event Collaboration Summary",
    description="Summarize attendee state for a shared calendar event so agents can verify collaboration and participation.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def apple_event_collaboration_summary(event_id: str) -> EventCollaborationResponse | AppleErrorResponse:
    event = calendar_get_event(event_id)
    if isinstance(event, CalendarErrorResponse):
        return _apple_error_response(event.error.error_code, event.error.message, event.error.suggestion)
    attendees = [_to_jsonable(attendee) for attendee in (event.event.attendees or [])]
    accepted_count = sum(1 for attendee in attendees if attendee.get("status") == "accepted")
    tentative_count = sum(1 for attendee in attendees if attendee.get("status") == "tentative")
    declined_count = sum(1 for attendee in attendees if attendee.get("status") == "declined")
    pending_count = sum(1 for attendee in attendees if attendee.get("status") == "pending")
    return EventCollaborationResponse(
        event_id=event.event.event_id,
        title=event.event.title,
        calendar_name=event.event.calendar_name,
        attendee_count=len(attendees),
        accepted_count=accepted_count,
        tentative_count=tentative_count,
        declined_count=declined_count,
        pending_count=pending_count,
        attendees=attendees,
    )


def apple_suggest_mailboxes(query: str | None = None, limit: int | str = 25) -> SuggestionListResponse:
    response = mail_list_mailboxes()
    if isinstance(response, MailErrorResponse):
        return SuggestionListResponse(domain="mail", suggestions=[], count=0)
    values = [f"{item.account} / {item.name}" for item in response.mailboxes]
    suggestions = _filter_text(values, query=query, limit=_coerce_int_arg("limit", limit, minimum=1))
    return SuggestionListResponse(domain="mail", suggestions=suggestions, count=len(suggestions))


def apple_suggest_calendars(query: str | None = None, limit: int | str = 25) -> SuggestionListResponse:
    response = calendar_list_calendars()
    values = [] if not getattr(response, "ok", False) else [f"{item.calendar_id} / {item.name}" for item in response.calendars]
    suggestions = _filter_text(values, query=query, limit=_coerce_int_arg("limit", limit, minimum=1))
    return SuggestionListResponse(domain="calendar", suggestions=suggestions, count=len(suggestions))


def apple_suggest_reminder_lists(query: str | None = None, limit: int | str = 25) -> SuggestionListResponse:
    response = reminders_list_lists()
    values = [] if not getattr(response, "ok", False) else [f"{item.list_id} / {item.title}" for item in response.lists]
    suggestions = _filter_text(values, query=query, limit=_coerce_int_arg("limit", limit, minimum=1))
    return SuggestionListResponse(domain="reminders", suggestions=suggestions, count=len(suggestions))


def apple_suggest_shortcuts(query: str | None = None, limit: int | str = 25) -> SuggestionListResponse:
    response = shortcuts_list_shortcuts()
    values = [] if not getattr(response, "ok", False) else [item.name for item in response.shortcuts]
    suggestions = _filter_text(values, query=query, limit=_coerce_int_arg("limit", limit, minimum=1))
    return SuggestionListResponse(domain="shortcuts", suggestions=suggestions, count=len(suggestions))


def apple_suggest_note_folders(query: str | None = None, limit: int | str = 25) -> SuggestionListResponse:
    response = notes_list_folders(limit=100, offset=0)
    values = [] if not getattr(response, "ok", False) else [f"{item.folder_id} / {item.account_name} / {item.name}" for item in response.folders]
    suggestions = _filter_text(values, query=query, limit=_coerce_int_arg("limit", limit, minimum=1))
    return SuggestionListResponse(domain="notes", suggestions=suggestions, count=len(suggestions))


def apple_suggest_message_conversations(query: str | None = None, limit: int | str = 25) -> SuggestionListResponse:
    response = messages_list_conversations(limit=100, offset=0)
    values = []
    if getattr(response, "ok", False):
        for item in response.conversations:
            label = item.display_name or ", ".join(participant.address for participant in item.participants) or item.chat_id
            values.append(f"{item.chat_id} / {label}")
    suggestions = _filter_text(values, query=query, limit=_coerce_int_arg("limit", limit, minimum=1))
    return SuggestionListResponse(domain="messages", suggestions=suggestions, count=len(suggestions))


def apple_suggest_contacts(query: str | None = None, limit: int | str = 25) -> SuggestionListResponse:
    response = contacts_search_contacts(query=query or "", limit=100) if query else contacts_list_contacts(limit=100, offset=0)
    values = []
    if getattr(response, "ok", False):
        for item in response.contacts:
            primary = item.phones[0].value if item.phones else (item.emails[0].value if item.emails else "")
            values.append(f"{item.contact_id} / {item.name} / {primary}")
    suggestions = _filter_text(values, query=query, limit=_coerce_int_arg("limit", limit, minimum=1))
    return SuggestionListResponse(domain="contacts", suggestions=suggestions, count=len(suggestions))


def apple_suggest_files(query: str | None = None, limit: int | str = 25) -> SuggestionListResponse:
    normalized_limit = _coerce_int_arg("limit", limit, minimum=1)
    response = files_search_files(query=query or "", limit=normalized_limit) if query else files_recent_files(limit=normalized_limit)
    values = []
    if getattr(response, "ok", False):
        values = [item.path for item in response.entries]
    suggestions = _filter_text(values, query=query, limit=normalized_limit)
    return SuggestionListResponse(domain="files", suggestions=suggestions, count=len(suggestions))


def apple_suggest_running_apps(query: str | None = None, limit: int | str = 25) -> SuggestionListResponse:
    normalized_limit = _coerce_int_arg("limit", limit, minimum=1)
    response = system_list_running_apps()
    values = [] if not getattr(response, "ok", False) else [item.name for item in response.apps]
    suggestions = _filter_text(values, query=query, limit=normalized_limit)
    return SuggestionListResponse(domain="system", suggestions=suggestions, count=len(suggestions))


def apple_suggest_places(query: str | None = None, limit: int | str = 10) -> SuggestionListResponse:
    normalized_limit = _coerce_int_arg("limit", limit, minimum=1)
    if not query:
        return SuggestionListResponse(domain="maps", suggestions=[], count=0)
    response = maps_search_places(query=query, limit=normalized_limit)
    values = []
    if getattr(response, "ok", False):
        values = [f"{item.name} / {item.address or ''}".strip() for item in response.places]
    suggestions = _filter_text(values, query=query, limit=normalized_limit)
    return SuggestionListResponse(domain="maps", suggestions=suggestions, count=len(suggestions))


for _name, _fn in (
    ("Apple Suggest Mailboxes", apple_suggest_mailboxes),
    ("Apple Suggest Calendars", apple_suggest_calendars),
    ("Apple Suggest Reminder Lists", apple_suggest_reminder_lists),
    ("Apple Suggest Shortcuts", apple_suggest_shortcuts),
    ("Apple Suggest Contacts", apple_suggest_contacts),
    ("Apple Suggest Note Folders", apple_suggest_note_folders),
    ("Apple Suggest Message Conversations", apple_suggest_message_conversations),
    ("Apple Suggest Files", apple_suggest_files),
    ("Apple Suggest Running Apps", apple_suggest_running_apps),
    ("Apple Suggest Places", apple_suggest_places),
):
    mcp.tool(
        title=_name,
        description=f"{_name} using the current Apple data surfaces. This is a completion fallback for clients without MCP completion support.",
        annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
        structured_output=True,
    )(_fn)


@mcp.tool(
    title="Apple Permission Guide",
    description="Explain how to grant the Apple permissions needed by a given Apple domain on macOS.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def apple_permission_guide(domain: str = "all") -> PermissionGuideResponse:
    return _permission_guide(domain)


@mcp.tool(
    title="Apple Recheck Permissions",
    description="Recheck Apple domain health after the user changes macOS permissions, and notify the client that Apple resources changed.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=False),
    structured_output=True,
)
async def apple_recheck_permissions(ctx: Context) -> AppleHealthResponse:
    await ctx.report_progress(10, 100, "Rechecking Apple permissions")
    response = apple_health()
    await ctx.report_progress(80, 100, "Refreshing Apple resources")
    await _notify_apple_resource_updates(ctx, "apple://overview", "apple://today", list_changed=True)
    await ctx.report_progress(100, 100, "Done")
    return response


@mcp.tool(
    title="Apple Send Message Interactive",
    description="Send an Apple Messages message, asking for missing recipient or text when needed.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=True),
    structured_output=True,
)
async def apple_send_message_interactive(
    recipient: str | None = None,
    text: str | None = None,
    service_name: str | None = None,
    ctx: Context | None = None,
) -> SendResponse | MessagesErrorResponse:
    if ctx is not None and (not recipient or not text):
        result = await ctx.elicit(
            message="I need the missing Messages details before I can send this.",
            schema=MessageInputRequest,
        )
        if result.action != "accept" or result.data is None:
            return MessagesErrorResponse(
                error=MessagesToolError(
                    error_code="USER_CANCELLED",
                    message="The user did not provide the missing Messages details.",
                    suggestion="Retry with recipient and text.",
                )
            )
        recipient = result.data.recipient
        text = result.data.text
        service_name = result.data.service_name if service_name is None else service_name
    if not recipient or not text:
        return MessagesErrorResponse(
            error=MessagesToolError(
                error_code="MISSING_INPUT",
                message="recipient and text are required.",
                suggestion="Provide recipient and text, or use a client that supports MCP elicitation.",
            )
        )
    if not _looks_like_message_address(recipient):
        resolved = contacts_resolve_message_recipient(query=recipient, channel="any")
        if isinstance(resolved, ContactsErrorResponse):
            return MessagesErrorResponse(
                error=MessagesToolError(
                    error_code=resolved.error.error_code,
                    message=resolved.error.message,
                    suggestion=resolved.error.suggestion,
                )
            )
        recipient = resolved.recipient_value
    return messages_send_message(recipient=recipient, text=text, service_name=service_name)


@mcp.tool(
    title="Apple Create Event Interactive",
    description="Create a Calendar event, asking for missing event details when needed.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
async def apple_create_event_interactive(
    title: str | None = None,
    start_iso: str | None = None,
    end_iso: str | None = None,
    calendar_id: str | None = None,
    notes: str | None = None,
    location: str | None = None,
    all_day: bool = False,
    ctx: Context | None = None,
) -> EventResponse | CalendarErrorResponse:
    if calendar_id is None:
        try:
            preferences = _get_preferences()
        except StateStoreError:
            preferences = AssistantPreferences()
        if preferences.default_calendar_id is not None:
            calendar_id = preferences.default_calendar_id
    if ctx is not None and (not title or not start_iso or not end_iso or not calendar_id):
        result = await ctx.elicit(
            message="I need the missing Calendar event details before I can create the event.",
            schema=EventInputRequest,
        )
        if result.action != "accept" or result.data is None:
            return CalendarErrorResponse(
                error=CalendarToolError(
                    error_code="USER_CANCELLED",
                    message="The user did not provide the missing Calendar details.",
                    suggestion="Retry with title, start_iso, end_iso, and calendar_id.",
                )
            )
        title = result.data.title
        start_iso = result.data.start_iso
        end_iso = result.data.end_iso
        calendar_id = result.data.calendar_id
        notes = notes if notes is not None else result.data.notes
        location = location if location is not None else result.data.location
        all_day = all_day or result.data.all_day
    if not title or not start_iso or not end_iso or not calendar_id:
        return CalendarErrorResponse(
            error=CalendarToolError(
                error_code="MISSING_INPUT",
                message="title, start_iso, end_iso, and calendar_id are required.",
                suggestion="Provide the missing event fields, or use a client that supports MCP elicitation.",
            )
        )
    return calendar_create_event(
        title=title,
        start_iso=start_iso,
        end_iso=end_iso,
        calendar_id=calendar_id,
        notes=notes,
        location=location,
        all_day=all_day,
    )


@mcp.resource(
    "apple://overview",
    name="apple_overview",
    title="Apple Overview",
    description="Aggregated Apple ecosystem status across the standalone Apple MCP domains.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=1.0),
)
def apple_overview_resource() -> str:
    try:
        preferences_payload = _to_jsonable(_get_preferences())
    except StateStoreError as exc:
        preferences_payload = {
            "ok": False,
            "error_code": exc.error_code,
            "message": exc.message,
            "suggestion": exc.suggestion,
        }
    return json.dumps(
        {
            "health": _domain_health(),
            "preferences": preferences_payload,
            "resources": {
                "files": _safe_resource_call(files_recent_resource),
                "system": _safe_resource_call(system_status_resource),
                "system_settings": _safe_resource_call(system_settings_resource),
                "calendar": _safe_resource_call(calendar_calendars_resource),
                "reminders": _safe_resource_call(reminders_lists_resource),
                "messages": _safe_resource_call(messages_recent_resource),
                "contacts": _safe_resource_call(contacts_directory_resource),
                "notes": _safe_resource_call(notes_recent_resource),
                "shortcuts": _safe_resource_call(shortcuts_all_resource),
                "mail": _safe_resource_call(_mailboxes_resource),
                "maps": _safe_resource_call(maps_status_resource),
            },
        },
        indent=2,
        sort_keys=True,
        default=str,
    )


@mcp.resource(
    "apple://today",
    name="apple_today",
    title="Apple Today",
    description="Combined Apple Calendar, Reminders, and Messages today-oriented snapshot.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.95),
)
def apple_today_resource() -> str:
    return json.dumps(
        {
            "system_status": _safe_resource_call(system_status_resource),
            "system_settings": _safe_resource_call(system_settings_resource),
            "calendar_today": _safe_resource_call(calendar_events_today_resource),
            "reminders_today": _safe_resource_call(reminders_today_resource),
            "messages_unread": _safe_resource_call(messages_unread_resource),
            "notes_recent": _safe_resource_call(notes_recent_resource),
            "files_recent": _safe_resource_call(files_recent_resource),
        },
        indent=2,
        sort_keys=True,
        default=str,
    )


@mcp.prompt(
    name="apple_plan_day",
    title="Plan Apple Day",
    description="Plan the day using Calendar, Reminders, Messages, Mail, and Notes context.",
)
def apple_plan_day_prompt() -> str:
    return (
        "Use Apple Calendar, Apple Reminders, and recent Apple Messages to plan the day. "
        "Start with the Apple Today resource, then use the domain tools to fill gaps and produce a practical plan."
    )


@mcp.prompt(
    name="apple_triage_communications",
    title="Triage Apple Communications",
    description="Triage communications across Mail and Messages with Contacts-aware routing.",
)
def apple_triage_communications_prompt() -> str:
    return (
        "Use Apple Mail and Apple Messages together to identify important inbound communications, summarize what needs action, "
        "and propose the highest-priority replies or follow-ups."
    )


@mcp.prompt(
    name="apple_prepare_next_meeting",
    title="Prepare Next Meeting",
    description="Prepare for the next meeting using Calendar, Notes, Mail, and Messages context.",
)
def apple_prepare_next_meeting_prompt() -> str:
    return (
        "Use Apple Calendar for the next meeting, Apple Notes for related notes, Apple Messages or Mail for recent context, "
        "Apple Files for local documents, and Apple Maps when travel time matters. Return a concise prep brief with agenda, open threads, travel context, and action items."
    )


@mcp.prompt(
    name="apple_route_request",
    title="Route Apple Request",
    description="Route user requests across Apple app domains with the unified MCP decision rules.",
)
def apple_route_request_prompt() -> str:
    return (
        "Route Apple requests carefully. Use Contacts before Messages or Mail when the user names a person, confirm multiple matches, "
        "and omit service_name entirely on iMessage sends. Use Mail for email workflows, but remember search requires a query string and ask once if text versus email is unclear. "
        "Use Calendar for scheduled time and confirm date, time, duration, and title before writing. Use Reminders for due items and follow-ups, identify the available lists on first use, "
        "and require due_date values with timezone offsets like 2026-03-29T23:59:00-05:00. Use Notes for reference material, identify available accounts and folders on first use, and send time-sensitive items to Reminders or Calendar instead. "
        "For Shortcuts, list available shortcuts before running when the request is vague. Use Files before Mail, Messages, Notes, or Shortcuts when the user references a local document or attachment. "
        "Use System when the frontmost app, clipboard, notifications, or battery status affects the next action. Use Maps when a route, place lookup, or travel estimate affects scheduling or communication. "
        "As a quick disambiguation rule: due date or time goes to Reminders, reference material with no action goes to Notes, and requests involving another person usually go to Messages or Mail after Contacts resolution."
    )


@mcp.tool(
    title="Apple Health",
    description="Report aggregated health across the unified Apple ecosystem MCP domains.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def apple_health() -> AppleHealthResponse:
    settings = load_settings()
    return AppleHealthResponse(
        server_name=settings.server_name,
        version=settings.version,
        transport=settings.transport,
        domains=_domain_health(),
    )


@mcp.tool(
    title="Apple Overview",
    description="Return an aggregated Apple ecosystem overview using the standalone domain resources.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def apple_overview() -> AppleOverviewResponse:
    payload = json.loads(apple_overview_resource())
    return AppleOverviewResponse(overview=payload)


def messages_get_conversation(chat_id: str, limit: int | str = 50, offset: int | str = 0) -> ConversationResponse | MessagesErrorResponse:
    return _messages_get_conversation(
        chat_id=chat_id,
        limit=_coerce_int_arg("limit", limit, minimum=1),
        offset=_coerce_int_arg("offset", offset, minimum=0),
    )


@mcp.completion()
async def apple_completion(
    ref: types.PromptReference | types.ResourceTemplateReference,
    argument: types.CompletionArgument,
    context: types.CompletionContext | None,
) -> types.Completion | None:
    del context
    if isinstance(ref, types.ResourceTemplateReference):
        uri = str(ref.uri)
        if uri == "contacts://contact/{contact_id}" and argument.name == "contact_id":
            response = contacts_list_contacts(limit=50, offset=0)
            values = [] if not getattr(response, "ok", False) else [item.contact_id for item in response.contacts]
            return types.Completion(values=values, total=len(values), hasMore=False)
        if uri == "notes://note/{note_id}" and argument.name == "note_id":
            response = notes_list_notes(limit=50, offset=0)
            values = [] if not getattr(response, "ok", False) else [item.note_id for item in response.notes]
            return types.Completion(values=values, total=len(values), hasMore=False)
        if uri == "messages://conversation/{chat_id}" and argument.name == "chat_id":
            response = messages_list_conversations(limit=50, offset=0)
            values = [] if not getattr(response, "ok", False) else [item.chat_id for item in response.conversations]
            return types.Completion(values=values, total=len(values), hasMore=False)
        if uri == "shortcuts://folder/{folder_name}" and argument.name == "folder_name":
            response = shortcuts_list_folders()
            values = [] if not getattr(response, "ok", False) else [item.name for item in response.folders]
            return types.Completion(values=values, total=len(values), hasMore=False)
    return types.Completion(values=[], total=0, hasMore=False)


def _tool_annotations(name: str) -> ToolAnnotations:
    if any(marker in name for marker in ("health", "list_", "get_", "search_", "view_", "resolve_")):
        return ToolAnnotations(readOnlyHint=True, idempotentHint=True)
    if any(marker in name for marker in ("delete_", "send_message")):
        return ToolAnnotations(destructiveHint=True, idempotentHint=False, openWorldHint="send_message" in name)
    return ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=name in {"messages_reply_in_conversation", "mail_compose_draft"})


def _tool_title(name: str) -> str:
    return name.replace("_", " ").title()


def _tool_description(name: str) -> str:
    return f"Delegated Apple domain tool '{name}' exposed through Apple-Tools-MCP."


def _looks_like_message_address(value: str) -> bool:
    if "@" in value:
        return True
    digits = re.sub(r"\D+", "", value)
    return len(digits) >= 7


def _summarize_mail_results(query: str, limit: int) -> list[dict[str, Any]]:
    result = mail_search_messages(query=query, limit=limit)
    if isinstance(result, MailErrorResponse):
        return [{"error": result.error.message}]
    return [
        {
            "message_id": item.message_id,
            "subject": item.subject,
            "sender": item.sender,
            "date_received": item.date_received,
            "mailbox": item.mailbox,
            "unread": item.unread,
        }
        for item in result.results
    ]


def _build_daily_briefing_payload(mail_query: str, mail_limit: int) -> dict[str, Any]:
    today = json.loads(apple_today_resource())
    overview = json.loads(apple_overview_resource())
    mail_highlights = _summarize_mail_results(mail_query, mail_limit)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "kind": "daily_briefing",
        "summary": "Daily Apple briefing generated from today, overview, and Mail context.",
        "today": today,
        "mail_highlights": mail_highlights,
        "domain_health": overview["health"],
    }


def _build_weekly_briefing_payload(days: int, mail_query: str, mail_limit: int) -> dict[str, Any]:
    start = datetime.now().astimezone()
    upcoming = calendar_list_events(
        start_iso=start.isoformat(),
        end_iso=(start + timedelta(days=days)).isoformat(),
    )
    reminders = reminders_list_reminders(limit=25)
    mail_highlights = _summarize_mail_results(mail_query, mail_limit)
    calendar_payload = [] if isinstance(upcoming, CalendarErrorResponse) else [event.model_dump(mode="json") for event in upcoming.events]
    reminders_payload = [] if getattr(reminders, "ok", False) is not True else [item.model_dump(mode="json") for item in reminders.reminders]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "kind": "weekly_briefing",
        "days": days,
        "summary": f"Weekly Apple briefing generated for the next {days} days.",
        "calendar_events": calendar_payload,
        "reminders": reminders_payload,
        "mail_highlights": mail_highlights,
    }


def _build_triage_payload(mail_query: str, mail_limit: int, conversation_limit: int) -> dict[str, Any]:
    unread_messages = json.loads(messages_unread_resource())
    mail_hits = _summarize_mail_results(mail_query, mail_limit)
    conversations = messages_list_conversations(limit=conversation_limit, offset=0)
    conversations_payload = [] if isinstance(conversations, MessagesErrorResponse) else [item.model_dump(mode="json") for item in conversations.conversations]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "kind": "communications_triage",
        "summary": "Unread Messages and Mail search results prepared for triage.",
        "mail": mail_hits,
        "messages_unread": unread_messages,
        "recent_conversations": conversations_payload,
    }


async def _run_briefing_task(
    ctx: Context,
    status_message: str,
    immediate_response: str,
    payload_builder: Callable[[], dict[str, Any]],
) -> types.CreateTaskResult:
    experimental = ctx.request_context.experimental
    experimental.validate_task_mode(types.TASK_OPTIONAL)

    async def work(task: ServerTaskContext) -> types.CallToolResult:
        await task.update_status(status_message)
        payload = payload_builder()
        await task.update_status("Finalizing result")
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps(payload, indent=2, sort_keys=True))],
            structuredContent=payload,
            isError=False,
        )

    return await experimental.run_task(work, model_immediate_response=immediate_response)


def _task_tool_definitions() -> list[types.Tool]:
    return [
        types.Tool(
            name="apple_generate_daily_briefing",
            title="Apple Generate Daily Briefing",
            description="Generate a daily Apple briefing. Supports task-augmented execution for longer runs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "mail_query": {"type": "string", "default": "*"},
                    "mail_limit": {"type": "integer", "minimum": 1, "default": 5},
                },
            },
            annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
            execution=types.ToolExecution(taskSupport=types.TASK_OPTIONAL),
        ),
        types.Tool(
            name="apple_generate_weekly_briefing",
            title="Apple Generate Weekly Briefing",
            description="Generate a weekly Apple briefing. Supports task-augmented execution for longer runs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "minimum": 1, "maximum": 14, "default": 7},
                    "mail_query": {"type": "string", "default": "*"},
                    "mail_limit": {"type": "integer", "minimum": 1, "default": 5},
                },
            },
            annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
            execution=types.ToolExecution(taskSupport=types.TASK_OPTIONAL),
        ),
        types.Tool(
            name="apple_triage_communications_task",
            title="Apple Triage Communications Task",
            description="Generate a cross-app communications triage summary. Supports task-augmented execution.",
            inputSchema={
                "type": "object",
                "properties": {
                    "mail_query": {"type": "string", "default": "*"},
                    "mail_limit": {"type": "integer", "minimum": 1, "default": 10},
                    "conversation_limit": {"type": "integer", "minimum": 1, "default": 10},
                },
            },
            annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
            execution=types.ToolExecution(taskSupport=types.TASK_OPTIONAL),
        ),
    ]


async def _call_task_tool(name: str, arguments: dict[str, Any], ctx: Context) -> dict[str, Any] | types.CreateTaskResult:
    if name == "apple_generate_daily_briefing":
        mail_query = str(arguments.get("mail_query", "*") or "*")
        mail_limit = _coerce_int_arg("mail_limit", arguments.get("mail_limit", 5), minimum=1)
        if ctx.request_context.experimental.is_task:
            return await _run_briefing_task(
                ctx,
                "Collecting daily Apple context",
                "Generating daily Apple briefing",
                lambda: _build_daily_briefing_payload(mail_query, mail_limit),
            )
        return _build_daily_briefing_payload(mail_query, mail_limit)
    if name == "apple_generate_weekly_briefing":
        days = _coerce_int_arg("days", arguments.get("days", 7), minimum=1)
        mail_query = str(arguments.get("mail_query", "*") or "*")
        mail_limit = _coerce_int_arg("mail_limit", arguments.get("mail_limit", 5), minimum=1)
        if ctx.request_context.experimental.is_task:
            return await _run_briefing_task(
                ctx,
                "Collecting weekly Apple context",
                "Generating weekly Apple briefing",
                lambda: _build_weekly_briefing_payload(days, mail_query, mail_limit),
            )
        return _build_weekly_briefing_payload(days, mail_query, mail_limit)
    if name == "apple_triage_communications_task":
        mail_query = str(arguments.get("mail_query", "*") or "*")
        mail_limit = _coerce_int_arg("mail_limit", arguments.get("mail_limit", 10), minimum=1)
        conversation_limit = _coerce_int_arg("conversation_limit", arguments.get("conversation_limit", 10), minimum=1)
        if ctx.request_context.experimental.is_task:
            return await _run_briefing_task(
                ctx,
                "Collecting unread communication context",
                "Generating communication triage summary",
                lambda: _build_triage_payload(mail_query, mail_limit, conversation_limit),
            )
        return _build_triage_payload(mail_query, mail_limit, conversation_limit)
    raise ValueError(f"Unknown task tool: {name}")


async def _list_tools_with_task_support() -> list[types.Tool]:
    base_tools = await mcp.list_tools()
    existing = {tool.name for tool in base_tools}
    return [*base_tools, *[tool for tool in _task_tool_definitions() if tool.name not in existing]]


UNIFIED_TOOL_FUNCTIONS: list[Callable[..., Any]] = [
    mail_health,
    mail_list_mailboxes,
    mail_search_messages,
    mail_get_message,
    mail_get_thread,
    mail_compose_draft,
    mail_reply_message,
    mail_reply_latest_in_thread,
    mail_forward_message,
    mail_mark_message,
    mail_move_message,
    mail_archive_thread,
    mail_delete_message,
    mail_send_message,
    calendar_health,
    calendar_list_calendars,
    calendar_list_events,
    calendar_get_event,
    calendar_create_event,
    calendar_update_event,
    calendar_delete_event,
    reminders_health,
    reminders_list_lists,
    reminders_create_list,
    reminders_delete_list,
    reminders_list_reminders,
    reminders_get_reminder,
    reminders_create_reminder,
    reminders_update_reminder,
    reminders_complete_reminder,
    reminders_uncomplete_reminder,
    reminders_delete_reminder,
    shortcuts_health,
    shortcuts_list_shortcuts,
    shortcuts_list_folders,
    shortcuts_view_shortcut,
    shortcuts_run_shortcut,
    files_health,
    files_list_allowed_roots,
    files_list_directory,
    files_search_files,
    files_get_file_info,
    files_read_text_file,
    files_recent_files,
    files_create_folder,
    files_move_path,
    files_delete_path,
    system_health,
    system_status,
    system_get_battery,
    system_get_frontmost_app,
    system_list_running_apps,
    system_get_clipboard,
    system_list_settings_domains,
    system_get_appearance_settings,
    system_get_accessibility_settings,
    system_get_dock_settings,
    system_get_finder_settings,
    system_get_settings_snapshot,
    system_read_preference_domain,
    system_set_appearance_mode,
    system_set_show_all_extensions,
    system_set_show_hidden_files,
    system_set_finder_path_bar,
    system_set_finder_status_bar,
    system_set_dock_autohide,
    system_set_dock_show_recents,
    system_set_reduce_motion,
    system_set_increase_contrast,
    system_set_reduce_transparency,
    system_set_clipboard,
    system_show_notification,
    system_open_application,
    system_gui_list_menu_bar_items,
    system_gui_click_menu_path,
    system_gui_press_keys,
    system_gui_type_text,
    system_gui_click_button,
    system_gui_choose_popup_value,
    maps_health,
    maps_search_places,
    maps_get_directions,
    maps_build_maps_link,
    maps_open_directions_in_maps,
    contacts_health,
    contacts_list_contacts,
    contacts_create_contact,
    contacts_update_contact,
    contacts_delete_contact,
    contacts_search_contacts,
    contacts_get_contact,
    contacts_resolve_message_recipient,
    notes_health,
    notes_list_accounts,
    notes_list_folders,
    notes_list_notes,
    notes_get_note,
    notes_search_notes,
    notes_create_note,
    notes_append_to_note,
    notes_update_note,
    notes_delete_note,
    notes_move_note,
    notes_create_folder,
    notes_rename_folder,
    notes_delete_folder,
    notes_list_attachments,
    messages_health,
    messages_list_conversations,
    messages_get_conversation,
    messages_search_messages,
    messages_get_message,
    messages_list_attachments,
    messages_send_message,
    messages_reply_in_conversation,
    messages_send_attachment,
]

APPLE_AGENT_TOOL_NAMES = [
    "apple_health",
    "apple_overview",
    "apple_get_preferences",
    "apple_detect_defaults",
    "apple_update_preferences",
    "apple_update_contact_preferences",
    "apple_permission_guide",
    "apple_recheck_permissions",
    "apple_list_prompts",
    "apple_get_prompt",
    "apple_prepare_communication",
    "apple_preview_communication",
    "apple_preview_create_reminder_with_defaults",
    "apple_preview_create_note_with_defaults",
    "apple_preview_follow_up_from_mail",
    "apple_send_communication",
    "apple_send_message_interactive",
    "apple_create_event_interactive",
    "apple_preview_archive_message",
    "apple_archive_message",
    "apple_list_recent_actions",
    "apple_undo_action",
    "apple_create_reminder_with_defaults",
    "apple_create_note_with_defaults",
    "apple_capture_follow_up_from_mail",
    "apple_event_collaboration_summary",
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
]

REGISTERED_TOOL_NAMES = [*APPLE_AGENT_TOOL_NAMES, *[fn.__name__ for fn in UNIFIED_TOOL_FUNCTIONS]]

for tool_fn in UNIFIED_TOOL_FUNCTIONS:
    mcp.add_tool(
        tool_fn,
        name=tool_fn.__name__,
        title=_tool_title(tool_fn.__name__),
        description=_tool_description(tool_fn.__name__),
        annotations=_tool_annotations(tool_fn.__name__),
        structured_output=True,
    )

mcp.resource(
    "mail://mailboxes",
    name="mailboxes_snapshot",
    title="Mailboxes",
    description="Current Apple Mail mailboxes.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.9),
)(_mailboxes_resource)

mcp.resource(
    "files://allowed-roots",
    name="files_allowed_roots",
    title="Allowed File Roots",
    description="The file system roots this MCP server is allowed to access.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.85),
)(files_allowed_roots_resource)

mcp.resource(
    "files://recent",
    name="files_recent",
    title="Recent Files",
    description="A compact snapshot of recently modified files inside the allowed roots.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.8),
)(files_recent_resource)

mcp.resource(
    "system://status",
    name="system_status",
    title="System Status",
    description="A compact macOS system status snapshot.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.8),
)(system_status_resource)

mcp.resource(
    "system://settings",
    name="system_settings",
    title="System Settings Snapshot",
    description="A read-only snapshot of appearance, accessibility, Dock, and Finder settings.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.78),
)(system_settings_resource)

mcp.resource(
    "system://applications",
    name="system_applications",
    title="Running Applications",
    description="Currently running foreground applications on macOS.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.7),
)(system_applications_resource)

mcp.resource(
    "maps://status",
    name="maps_status",
    title="Maps Status",
    description="Apple Maps helper availability and supported transport modes.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.7),
)(maps_status_resource)

mcp.resource(
    "contacts://directory",
    name="contacts_directory",
    title="Contacts Directory",
    description="Current Apple Contacts directory snapshot.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.85),
)(contacts_directory_resource)

mcp.resource(
    "contacts://contact/{contact_id}",
    name="contacts_detail",
    title="Contact Detail",
    description="A single Apple Contacts record.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.75),
)(contacts_contact_resource)

mcp.resource(
    "calendar://calendars",
    name="calendar_list_snapshot",
    title="Calendar List",
    description="Current Apple Calendar calendars.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.9),
)(calendar_calendars_resource)

mcp.resource(
    "calendar://events/today",
    name="calendar_today_snapshot",
    title="Today's Events",
    description="A compact snapshot of today's Apple Calendar events.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.8),
)(calendar_events_today_resource)

mcp.resource(
    "reminders://lists",
    name="reminder_lists",
    title="Reminder Lists",
    description="Current Apple Reminders lists.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.9),
)(reminders_lists_resource)

mcp.resource(
    "reminders://today",
    name="reminders_today",
    title="Upcoming Reminders",
    description="A compact snapshot of upcoming Apple Reminders tasks.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.8),
)(reminders_today_resource)

mcp.resource(
    "shortcuts://all",
    name="shortcuts_all",
    title="All Shortcuts",
    description="Current Apple Shortcuts folders and shortcuts.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.8),
)(shortcuts_all_resource)

mcp.resource(
    "shortcuts://folder/{folder_name}",
    name="shortcuts_folder",
    title="Shortcuts Folder",
    description="Shortcuts in a specific Apple Shortcuts folder.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.7),
)(shortcuts_folder_resource)

mcp.resource(
    "notes://folders",
    name="notes_folders_snapshot",
    title="Note Folders",
    description="Current Apple Notes folders.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.8),
)(notes_folders_resource)

mcp.resource(
    "notes://recent",
    name="notes_recent_snapshot",
    title="Recent Notes",
    description="A compact snapshot of recently modified Apple Notes notes.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.8),
)(notes_recent_resource)

mcp.resource(
    "notes://note/{note_id}",
    name="notes_note_detail",
    title="Note Detail",
    description="A single Apple Notes note.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.7),
)(notes_note_resource)

mcp.resource(
    "messages://conversations/recent",
    name="messages_recent",
    title="Recent Conversations",
    description="Recent Apple Messages conversations when history access is available.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.8),
)(messages_recent_resource)

mcp.resource(
    "messages://conversation/{chat_id}",
    name="messages_conversation",
    title="Conversation Snapshot",
    description="A paginated Apple Messages conversation snapshot.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.7),
)(messages_conversation_resource)

mcp.resource(
    "messages://unread",
    name="messages_unread",
    title="Unread Conversations",
    description="Unread Apple Messages conversations when history access is available.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.7),
)(messages_unread_resource)

mcp.prompt(name="mail_inbox_triage", title="Triage Inbox", description="Review inbox state and suggest the next Mail actions.")(mail_inbox_triage_prompt_text)
mcp.prompt(name="mail_draft_reply", title="Draft Reply", description="Find the right email and draft a reply with Apple Mail.")(mail_draft_reply_prompt_text)
mcp.prompt(name="calendar_plan_today", title="Plan Today", description="Review today in Apple Calendar and build a concise plan.")(calendar_plan_today_prompt)
mcp.prompt(name="calendar_prepare_agenda", title="Prepare Agenda", description="Prepare a meeting agenda from Apple Calendar context.")(calendar_prepare_agenda_prompt)
mcp.prompt(name="reminders_plan_today", title="Plan Today", description="Plan today using Apple Reminders lists and due items.")(reminders_plan_today_prompt)
mcp.prompt(name="reminders_inbox_triage", title="Triage Reminder Inbox", description="Triage Apple Reminders and organize follow-up work.")(reminders_inbox_triage_prompt)
mcp.prompt(name="files_prepare_attachment", title="Prepare Attachment", description="Locate the right local file before attaching or referencing it.")(files_prepare_attachment_prompt)
mcp.prompt(name="files_organize_workspace", title="Organize Workspace", description="Inspect and organize local folders inside the allowed roots.")(files_organize_workspace_prompt)
mcp.prompt(name="system_capture_context", title="Capture System Context", description="Capture frontmost app, battery, and running app context before acting.")(system_capture_context_prompt)
mcp.prompt(name="maps_plan_route", title="Plan Route", description="Find the right place and estimate travel before scheduling or messaging.")(maps_plan_route_prompt)
mcp.prompt(name="shortcuts_choose_and_run", title="Choose and Run Shortcut", description="Choose the right Apple Shortcut before running it.")(shortcuts_choose_and_run_prompt)
mcp.prompt(name="shortcuts_run_with_input", title="Run Shortcut With Structured Input", description="Prepare structured input for an Apple Shortcut run.")(shortcuts_run_with_input_prompt)
mcp.prompt(name="shortcuts_follow_up", title="Use Shortcut Output", description="Interpret Apple Shortcut output and decide the next action.")(shortcuts_follow_up_prompt)
mcp.prompt(name="notes_find_reference", title="Find Referenced Note", description="Find the right Apple Note for reference material.")(notes_find_reference_prompt)
mcp.prompt(name="notes_organize_topic", title="Organize Notes by Topic", description="Organize Apple Notes around a topic or project.")(notes_organize_topic_prompt)
mcp.prompt(name="notes_create_from_conversation", title="Create Note from Conversation", description="Create a note from conversation context.")(notes_create_from_conversation_prompt)
mcp.prompt(name="notes_cleanup", title="Clean Up Notes", description="Clean up and consolidate Apple Notes content.")(notes_cleanup_prompt)
mcp.prompt(name="messages_triage_unread", title="Triage Unread", description="Review unread Apple Messages and prioritize replies.")(messages_triage_unread_prompt)
mcp.prompt(name="messages_summarize_thread", title="Summarize Thread", description="Summarize an Apple Messages conversation thread.")(messages_summarize_thread_prompt)
mcp.prompt(name="messages_draft_reply", title="Draft Reply", description="Draft an Apple Messages reply from thread context.")(messages_draft_reply_prompt)
mcp.prompt(name="contacts_prepare_message_recipient", title="Prepare Message Recipient", description="Resolve the right Apple Contacts recipient before messaging.")(contacts_prepare_message_recipient_prompt)


@mcp.tool(
    title="Apple List Prompts",
    description="Fallback prompt discovery tool for clients that only support tools.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
async def apple_list_prompts() -> dict[str, Any]:
    prompts = await mcp.list_prompts()
    return {
        "ok": True,
        "prompts": [
            {
                "name": prompt.name,
                "title": prompt.title,
                "description": prompt.description,
                "arguments": [argument.model_dump(mode="json") for argument in getattr(prompt, "arguments", [])],
            }
            for prompt in prompts
        ],
        "count": len(prompts),
    }


@mcp.tool(
    title="Apple Get Prompt",
    description="Fallback prompt rendering tool for clients that only support tools.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
async def apple_get_prompt(name: str, arguments_json: str | None = None) -> dict[str, Any] | AppleErrorResponse:
    try:
        arguments = json.loads(arguments_json) if arguments_json else None
    except json.JSONDecodeError as exc:
        return _apple_error_response("INVALID_PROMPT_ARGUMENTS", f"arguments_json is not valid JSON: {exc}", "Pass a JSON object string or omit arguments_json.")
    try:
        prompt = await mcp.get_prompt(name, arguments)
    except Exception as exc:
        return _apple_error_response("PROMPT_LOOKUP_FAILED", str(exc), "Call apple_list_prompts first to inspect the available prompt names.")
    return {
        "ok": True,
        "name": name,
        "description": getattr(prompt, "description", None),
        "messages": _serialize_prompt_messages(prompt.messages),
        "message_count": len(prompt.messages),
    }


@mcp._mcp_server.subscribe_resource()
async def _apple_subscribe_resource(uri: AnyUrl) -> None:
    _SUBSCRIBED_RESOURCES.add(str(uri))


@mcp._mcp_server.unsubscribe_resource()
async def _apple_unsubscribe_resource(uri: AnyUrl) -> None:
    _SUBSCRIBED_RESOURCES.discard(str(uri))


mcp._mcp_server.experimental.enable_tasks()


@mcp._mcp_server.list_tools()
async def _apple_list_tools_with_extensions(_: types.ListToolsRequest) -> list[types.Tool]:
    return await _list_tools_with_task_support()


@mcp._mcp_server.call_tool(validate_input=False)
async def _apple_call_tool_with_extensions(name: str, arguments: dict[str, Any]) -> Any:
    if name in {tool.name for tool in _task_tool_definitions()}:
        return await _call_task_tool(name, arguments or {}, mcp.get_context())
    return await mcp.call_tool(name, arguments or {})


def main() -> None:
    settings = load_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))
    conformance_mode = os.environ.get("APPLE_AGENT_MCP_CONFORMANCE_MODE", "").strip().lower() in {"1", "true", "yes", "on"}
    if conformance_mode:
        enable_conformance_mode(mcp)
    if settings.transport == "stdio":
        mcp.run(transport="stdio")
        return
    mcp.settings.host = settings.host
    mcp.settings.port = settings.port
    mcp.settings.log_level = settings.log_level
    mcp.settings.stateless_http = False if conformance_mode else True
    mcp.settings.json_response = False if conformance_mode else True
    mcp.run(transport="streamable-http")
