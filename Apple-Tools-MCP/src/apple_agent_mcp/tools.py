from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json
import logging
import re
from typing import Any, Callable

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import Annotations, ToolAnnotations
from pydantic import BaseModel

from apple_agent_mcp.bootstrap import ensure_domain_paths
from apple_agent_mcp.config import load_settings
from apple_agent_mcp.models import AppleHealthResponse, AppleOverviewResponse, PermissionGuideResponse, SuggestionListResponse

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
)
from apple_mail_mcp.tools import (  # noqa: E402
    mail_compose_draft as _mail_compose_draft,
    mail_draft_reply_prompt_text,
    mail_get_message as _mail_get_message,
    mail_health as _mail_health,
    mail_inbox_triage_prompt_text,
    mail_list_mailboxes as _mail_list_mailboxes,
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
    contacts_resolve_message_recipient,
    contacts_search_contacts,
)
from apple_contacts_mcp.models import ErrorResponse as ContactsErrorResponse  # noqa: E402
from apple_notes_mcp.tools import (  # noqa: E402
    notes_cleanup_prompt,
    notes_create_folder,
    notes_create_from_conversation_prompt,
    notes_create_note,
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
from apple_reminders_mcp.tools import (  # noqa: E402
    reminders_complete_reminder,
    reminders_create_reminder,
    reminders_delete_reminder,
    reminders_get_reminder,
    reminders_health,
    reminders_inbox_triage_prompt,
    reminders_list_lists,
    reminders_list_reminders,
    reminders_lists_resource,
    reminders_plan_today_prompt,
    reminders_today_resource,
    reminders_uncomplete_reminder,
    reminders_update_reminder,
)
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

SERVER_INSTRUCTIONS = (
    "Use this server for unified Apple ecosystem access on macOS. "
    "Search here when the user wants one Apple-native entrypoint across Mail, Calendar, Reminders, Messages, Contacts, Notes, and Shortcuts. "
    "Prefer cross-app overview resources and prompts first, then use namespaced domain tools for specific actions."
)

mcp = FastMCP("Apple-Tools-MCP", instructions=SERVER_INSTRUCTIONS, json_response=True)

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


def _domain_health() -> dict[str, dict[str, Any]]:
    return {
        "mail": _to_jsonable(mail_health()),
        "calendar": _to_jsonable(calendar_health()),
        "reminders": _to_jsonable(reminders_health()),
        "messages": _to_jsonable(messages_health()),
        "contacts": _to_jsonable(contacts_health()),
        "notes": _to_jsonable(notes_health()),
        "shortcuts": _to_jsonable(shortcuts_health()),
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
        "all": PermissionGuideResponse(
            domain="all",
            can_prompt_in_app=True,
            requires_manual_system_settings=True,
            steps=[
                "Use the domain-specific guide for the app you want to authorize.",
                "Grant automation prompts when they appear.",
                "Grant Contacts access if you want to resolve recipients by contact name before messaging.",
                "Grant Full Disk Access manually for Apple Messages history access.",
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


def mail_compose_draft(
    to: list[str],
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    subject: str = "",
    body: str = "",
    attachments: list[str] | None = None,
) -> MailDraftRecord | MailErrorResponse:
    return _mail_compose_draft(
        to=to,
        cc=cc,
        bcc=bcc,
        subject=subject,
        body=body,
        attachments=attachments,
    )


def mail_send_message(
    to: list[str],
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    subject: str = "",
    body: str = "",
    attachments: list[str] | None = None,
) -> MailSendRecord | MailErrorResponse:
    return _mail_send_message(
        to=to,
        cc=cc,
        bcc=bcc,
        subject=subject,
        body=body,
        attachments=attachments,
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


for _name, _fn in (
    ("Apple Suggest Mailboxes", apple_suggest_mailboxes),
    ("Apple Suggest Calendars", apple_suggest_calendars),
    ("Apple Suggest Reminder Lists", apple_suggest_reminder_lists),
    ("Apple Suggest Shortcuts", apple_suggest_shortcuts),
    ("Apple Suggest Contacts", apple_suggest_contacts),
    ("Apple Suggest Note Folders", apple_suggest_note_folders),
    ("Apple Suggest Message Conversations", apple_suggest_message_conversations),
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
    await ctx.session.send_resource_list_changed()
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
    return json.dumps(
        {
            "health": _domain_health(),
            "resources": {
                "calendar": _safe_resource_call(calendar_calendars_resource),
                "reminders": _safe_resource_call(reminders_lists_resource),
                "messages": _safe_resource_call(messages_recent_resource),
                "contacts": _safe_resource_call(contacts_directory_resource),
                "notes": _safe_resource_call(notes_recent_resource),
                "shortcuts": _safe_resource_call(shortcuts_all_resource),
                "mail": _safe_resource_call(_mailboxes_resource),
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
            "calendar_today": _safe_resource_call(calendar_events_today_resource),
            "reminders_today": _safe_resource_call(reminders_today_resource),
            "messages_unread": _safe_resource_call(messages_unread_resource),
            "notes_recent": _safe_resource_call(notes_recent_resource),
        },
        indent=2,
        sort_keys=True,
        default=str,
    )


@mcp.prompt(name="apple_plan_day", title="Plan Apple Day")
def apple_plan_day_prompt() -> str:
    return (
        "Use Apple Calendar, Apple Reminders, and recent Apple Messages to plan the day. "
        "Start with the Apple Today resource, then use the domain tools to fill gaps and produce a practical plan."
    )


@mcp.prompt(name="apple_triage_communications", title="Triage Apple Communications")
def apple_triage_communications_prompt() -> str:
    return (
        "Use Apple Mail and Apple Messages together to identify important inbound communications, summarize what needs action, "
        "and propose the highest-priority replies or follow-ups."
    )


@mcp.prompt(name="apple_prepare_next_meeting", title="Prepare Next Meeting")
def apple_prepare_next_meeting_prompt() -> str:
    return (
        "Use Apple Calendar for the next meeting, Apple Notes for related notes, and Apple Messages or Mail for recent context. "
        "Return a concise prep brief with agenda, open threads, and action items."
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


UNIFIED_TOOL_FUNCTIONS: list[Callable[..., Any]] = [
    mail_health,
    mail_list_mailboxes,
    mail_search_messages,
    mail_get_message,
    mail_compose_draft,
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
    contacts_health,
    contacts_list_contacts,
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
]

APPLE_AGENT_TOOL_NAMES = [
    "apple_health",
    "apple_overview",
    "apple_permission_guide",
    "apple_recheck_permissions",
    "apple_send_message_interactive",
    "apple_create_event_interactive",
    "apple_suggest_mailboxes",
    "apple_suggest_calendars",
    "apple_suggest_reminder_lists",
    "apple_suggest_shortcuts",
    "apple_suggest_contacts",
    "apple_suggest_note_folders",
    "apple_suggest_message_conversations",
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

mcp.prompt(name="mail_inbox_triage", title="Triage Inbox")(mail_inbox_triage_prompt_text)
mcp.prompt(name="mail_draft_reply", title="Draft Reply")(mail_draft_reply_prompt_text)
mcp.prompt(name="calendar_plan_today", title="Plan Today")(calendar_plan_today_prompt)
mcp.prompt(name="calendar_prepare_agenda", title="Prepare Agenda")(calendar_prepare_agenda_prompt)
mcp.prompt(name="reminders_plan_today", title="Plan Today")(reminders_plan_today_prompt)
mcp.prompt(name="reminders_inbox_triage", title="Triage Reminder Inbox")(reminders_inbox_triage_prompt)
mcp.prompt(name="shortcuts_choose_and_run", title="Choose and Run Shortcut")(shortcuts_choose_and_run_prompt)
mcp.prompt(name="shortcuts_run_with_input", title="Run Shortcut With Structured Input")(shortcuts_run_with_input_prompt)
mcp.prompt(name="shortcuts_follow_up", title="Use Shortcut Output")(shortcuts_follow_up_prompt)
mcp.prompt(name="notes_find_reference", title="Find Referenced Note")(notes_find_reference_prompt)
mcp.prompt(name="notes_organize_topic", title="Organize Notes by Topic")(notes_organize_topic_prompt)
mcp.prompt(name="notes_create_from_conversation", title="Create Note from Conversation")(notes_create_from_conversation_prompt)
mcp.prompt(name="notes_cleanup", title="Clean Up Notes")(notes_cleanup_prompt)
mcp.prompt(name="messages_triage_unread", title="Triage Unread")(messages_triage_unread_prompt)
mcp.prompt(name="messages_summarize_thread", title="Summarize Thread")(messages_summarize_thread_prompt)
mcp.prompt(name="messages_draft_reply", title="Draft Reply")(messages_draft_reply_prompt)


def main() -> None:
    settings = load_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))
    if settings.transport == "stdio":
        mcp.run(transport="stdio")
        return
    mcp.run(
        transport="streamable-http",
        host=settings.host,
        port=settings.port,
        stateless_http=True,
        json_response=True,
    )
