from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Annotated

from mcp.server.mcpserver import Context
from mcp.types import Annotations, InputRequiredResult, PromptMessage, ToolAnnotations
from pydantic import Field

from apple_mcp_common.discovery import install_search_first_discovery
from apple_mcp_common.runtime import notify_resources_changed, require_loopback_host
from apple_mcp_common.server import AppleMCPServer
from apple_reminders_mcp.config import load_settings
from apple_reminders_mcp.models import (
    DeleteReminderListResponse,
    DeleteReminderResponse,
    ErrorResponse,
    HealthResponse,
    ReminderListItemsResponse,
    ReminderListMutationResponse,
    ReminderListResponse,
    ReminderResponse,
    ToolError,
)
from apple_reminders_mcp.permissions import SafetyError, ensure_action_allowed
from apple_reminders_mcp.reminders_bridge import RemindersBridge, RemindersBridgeError, build_bridge

SERVER_INSTRUCTIONS = (
    "Use this server for Apple Reminders task management on macOS. "
    "Search here when the user wants to inspect reminder lists, review upcoming tasks, create tasks, edit task details, complete tasks, or delete tasks. "
    "Prefer list and get tools before mutation tools when ids are unknown."
)

_LIST_ID_DESCRIPTION = "Reminder list ID returned by reminders_list_lists; pass it unchanged."
_REMINDER_ID_DESCRIPTION = "Reminder ID returned by reminders_list_reminders or reminders_get_reminder; pass it unchanged."
_DATE_FORMAT = "ISO 8601 datetime with Z or an offset (2026-10-22T09:00:00-05:00), or a date YYYY-MM-DD in the Mac's local time zone."
_DUE_DATE_DESCRIPTION = f"When the reminder is due. {_DATE_FORMAT}"
_DUE_ALL_DAY_DESCRIPTION = "True to keep only the date of due_date (no due time)."
_REMIND_AT_DESCRIPTION = f"When to show a notification; sets the reminder's single alert. {_DATE_FORMAT}"
_PRIORITY_DESCRIPTION = "Apple Reminders priority: 0 none, 1 high, 5 medium, 9 low."
_TAGS_DESCRIPTION = "Tags appended to the notes as #hashtags (leading # optional)."
_PARENT_DESCRIPTION = "Not supported: subtasks are unavailable through public APIs, so any value returns SUBTASKS_UNSUPPORTED. Omit it."
_OMIT_UNCHANGED = "Omit to leave unchanged."
_PROMPT_NAME_DESCRIPTION = "Prompt name from reminders_list_prompts."
_PROMPT_ARGUMENTS_DESCRIPTION = "Prompt arguments as a JSON object string; omit when the prompt takes none."

mcp = AppleMCPServer("Apple Reminders MCP", instructions=SERVER_INSTRUCTIONS, version=load_settings().version)


def _bridge() -> RemindersBridge:
    return build_bridge()


def _error_response(error_code: str, message: str, suggestion: str | None = None) -> ErrorResponse:
    return ErrorResponse(error=ToolError(error_code=error_code, message=message, suggestion=suggestion))


def _resource_json(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, default=str)


def _coerce_int_arg(name: str, value: int | str, *, minimum: int | None = None) -> int:
    try:
        normalized = int(str(value).strip()) if isinstance(value, str) else int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if minimum is not None and normalized < minimum:
        comparator = "greater than zero" if minimum == 1 else f"at least {minimum}"
        raise ValueError(f"{name} must be {comparator}")
    return normalized


def _capabilities() -> tuple[list[str], bool, bool]:
    source_exists, binary_exists = _bridge().helper_available()
    return (
        [
            "list_lists",
            "create_list",
            "delete_list",
            "list_reminders",
            "get_reminder",
            "create_reminder",
            "update_reminder",
            "complete_reminder",
            "uncomplete_reminder",
            "delete_reminder",
            "resources",
            "prompts",
        ],
        source_exists,
        binary_exists,
    )


def _reminder_owner_list(reminder_id: str) -> str | None:
    detail = _bridge().get_reminder(reminder_id)
    return detail.list_name


def _list_title(list_id: str) -> str:
    for item in _bridge().list_lists():
        if item.list_id == list_id:
            return item.title
    raise RemindersBridgeError("LIST_NOT_FOUND", f"No reminder list matched '{list_id}'.", "List reminder lists first to discover valid ids.")


def _list_visible(title: str) -> bool:
    allowed = load_settings().allowed_lists
    return not allowed or title in allowed


def _reminder_due_sort_key(item):
    # EventKit emits date-only values in the Mac's local time zone and timed
    # values with UTC offsets. Naive timestamp() resolves the due date's local
    # offset (including DST), matching Calendar.current's midnight ordering.
    try:
        due = datetime.fromisoformat(item.due_date).timestamp() if item.due_date else float("inf")
    except ValueError:
        due = float("inf")
    return due, item.title.casefold()


def _scoped_reminders(*, list_id: str | None = None, limit: int = 100, **filters):
    if list_id is not None:
        ensure_action_allowed("reminders_list_reminders", _list_title(list_id))
    if list_id is None and load_settings().allowed_lists:
        reminders = []
        for item in _bridge().list_lists():
            if _list_visible(item.title):
                reminders.extend(_bridge().list_reminders(list_id=item.list_id, limit=limit, **filters))
        reminders.sort(key=_reminder_due_sort_key)
    else:
        reminders = _bridge().list_reminders(list_id=list_id, limit=limit, **filters)
    return [item for item in reminders if _list_visible(item.list_name)][:limit]


@mcp.resource(
    "reminders://lists",
    name="reminder_lists",
    title="Reminder Lists",
    description="Current Apple Reminders lists.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.9),
)
def reminders_lists_resource() -> str:
    lists = [item for item in _bridge().list_lists() if _list_visible(item.title)]
    return _resource_json({"lists": [item.model_dump() for item in lists], "count": len(lists)})


@mcp.resource(
    "reminders://today",
    name="reminders_today",
    title="Upcoming Reminders",
    description="A compact snapshot of upcoming Apple Reminders tasks.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.8),
)
def reminders_today_resource() -> str:
    reminders = _scoped_reminders(include_completed=False, limit=25)
    return _resource_json({"reminders": [item.model_dump() for item in reminders], "count": len(reminders)})


@mcp.prompt(name="reminders_plan_today", title="Plan Today")
def reminders_plan_today_prompt() -> str:
    return (
        "Use Apple Reminders to review upcoming open tasks, identify what is due soon, "
        "and propose a practical plan for today. Start by checking reminder lists and upcoming reminders."
    )


@mcp.prompt(name="reminders_inbox_triage", title="Triage Reminder Inbox")
def reminders_inbox_triage_prompt() -> str:
    return (
        "Review reminder lists for uncategorized or overdue work, then suggest cleanup actions. "
        "Prefer listing reminders first, then propose edits or completions only when justified."
    )


@mcp.tool(
    title="Reminders Health",
    description="Report the active Apple Reminders MCP server configuration.",
    annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
    structured_output=True,
)
def reminders_health() -> HealthResponse:
    settings = load_settings()
    capabilities, helper_available, helper_compiled = _capabilities()
    return HealthResponse(
        server_name=settings.server_name,
        version=settings.version,
        safety_mode=settings.safety_mode,
        capabilities=capabilities,
        helper_available=helper_available,
        helper_compiled=helper_compiled,
    )


@mcp.tool(
    title="Reminders Permission Guide",
    description="Explain how to grant Apple Reminders permission on macOS.",
    annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
    structured_output=True,
)
def reminders_permission_guide() -> dict[str, object]:
    return {
        "ok": True,
        "domain": "reminders",
        "can_prompt_in_app": True,
        "requires_manual_system_settings": False,
        "steps": [
            "Call a Reminders tool from this MCP server.",
            "Approve the macOS Reminders access prompt when it appears.",
            "If access was denied before, re-enable it in System Settings > Privacy & Security > Reminders.",
        ],
    }


@mcp.tool(
    title="Reminders Recheck Permissions",
    description="Recheck Reminders access after the user changes macOS permissions, and notify the client that Reminders resources changed.",
    annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=False, open_world_hint=False),
    structured_output=True,
)
async def reminders_recheck_permissions(ctx: Context) -> HealthResponse:
    await ctx.report_progress(25, 100, "Rechecking Reminders access")
    response = reminders_health()
    await notify_resources_changed(ctx)
    await ctx.report_progress(100, 100, "Done")
    return response


@mcp.tool(
    title="List Reminder Lists",
    description="List available Apple Reminders lists.",
    annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
    structured_output=True,
)
def reminders_list_lists() -> ReminderListResponse | ErrorResponse:
    try:
        ensure_action_allowed("reminders_list_lists")
        lists = [item for item in _bridge().list_lists() if _list_visible(item.title)]
        return ReminderListResponse(lists=lists, count=len(lists))
    except (SafetyError, RemindersBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Create Reminder List",
    description="Create a new Apple Reminders list.",
    annotations=ToolAnnotations(destructive_hint=False, idempotent_hint=False, open_world_hint=False),
    structured_output=True,
)
def reminders_create_list(title: Annotated[str, Field(description="Name of the new reminder list.")]) -> ReminderListMutationResponse | ErrorResponse:
    if not title.strip():
        return _error_response("INVALID_INPUT", "title must not be empty", "Provide a non-empty title.")
    try:
        ensure_action_allowed("reminders_create_list", title.strip())
        return _bridge().create_list(title=title.strip())
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except RemindersBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Delete Reminder List",
    description="Delete a reminder list entirely. Requires full_access safety mode.",
    annotations=ToolAnnotations(destructive_hint=True, idempotent_hint=True, open_world_hint=False),
    structured_output=True,
)
def reminders_delete_list(list_id: Annotated[str, Field(description=f"{_LIST_ID_DESCRIPTION} Deletes the list and all its reminders.")]) -> DeleteReminderListResponse | ErrorResponse:
    try:
        ensure_action_allowed("reminders_delete_list")
        try:
            title = _list_title(list_id)
        except RemindersBridgeError as exc:
            if exc.error_code == "LIST_NOT_FOUND":
                return DeleteReminderListResponse(list_id=list_id, deleted=False)
            raise
        ensure_action_allowed("reminders_delete_list", title)
        return _bridge().delete_list(list_id=list_id)
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except RemindersBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="List Reminders",
    description="List reminders with optional list and due-date filters.",
    annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
    structured_output=True,
)
def reminders_list_reminders(
    list_id: Annotated[str | None, Field(description=f"{_LIST_ID_DESCRIPTION} Omit to search every visible list.")] = None,
    include_completed: Annotated[bool, Field(description="Include completed reminders; false returns only open ones.")] = True,
    limit: Annotated[int | str, Field(description="Maximum number of reminders to return (1 or more).")] = 100,
    search: Annotated[str | None, Field(description="Case-insensitive text matched against reminder titles and notes.")] = None,
    due_after: Annotated[
        str | None, Field(description=f"Only reminders due at or after this time; undated reminders are excluded. {_DATE_FORMAT}")
    ] = None,
    due_before: Annotated[
        str | None, Field(description=f"Only reminders due at or before this time; undated reminders are excluded. {_DATE_FORMAT}")
    ] = None,
) -> ReminderListItemsResponse | ErrorResponse:
    try:
        limit_value = _coerce_int_arg("limit", limit, minimum=1)
        ensure_action_allowed("reminders_list_reminders")
        reminders = _scoped_reminders(
            list_id=list_id,
            include_completed=include_completed,
            limit=limit_value,
            search=search,
            due_after=due_after,
            due_before=due_before,
        )
        return ReminderListItemsResponse(reminders=reminders, count=len(reminders))
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except RemindersBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except ValueError as exc:
        return _error_response("INVALID_INPUT", str(exc), "Provide a positive limit.")


@mcp.tool(
    title="Get Reminder",
    description="Fetch full details for a reminder by reminder_id.",
    annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
    structured_output=True,
)
def reminders_get_reminder(reminder_id: Annotated[str, Field(description=_REMINDER_ID_DESCRIPTION)]) -> ReminderResponse | ErrorResponse:
    try:
        detail = _bridge().get_reminder(reminder_id)
        ensure_action_allowed("reminders_get_reminder", detail.list_name)
        return ReminderResponse(reminder=detail)
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except RemindersBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Create Reminder",
    description="Create a new reminder in a specific Apple Reminders list.",
    annotations=ToolAnnotations(destructive_hint=False, idempotent_hint=False, open_world_hint=False),
    structured_output=True,
)
def reminders_create_reminder(
    title: Annotated[str, Field(description="Reminder title.")],
    list_id: Annotated[str, Field(description=_LIST_ID_DESCRIPTION)],
    notes: Annotated[str | None, Field(description="Plain-text notes.")] = None,
    due_date: Annotated[str | None, Field(description=_DUE_DATE_DESCRIPTION)] = None,
    due_all_day: Annotated[bool, Field(description=_DUE_ALL_DAY_DESCRIPTION)] = False,
    remind_at: Annotated[str | None, Field(description=_REMIND_AT_DESCRIPTION)] = None,
    priority: Annotated[int | str, Field(description=_PRIORITY_DESCRIPTION)] = 0,
    parent_reminder_id: Annotated[str | None, Field(description=_PARENT_DESCRIPTION)] = None,
    tags: Annotated[list[str] | None, Field(description=_TAGS_DESCRIPTION)] = None,
) -> ReminderResponse | ErrorResponse:
    try:
        if not title.strip():
            raise ValueError("title must not be empty")
        if parent_reminder_id is not None:
            return _error_response(
                "SUBTASKS_UNSUPPORTED",
                "Apple Reminders subtasks are not available through the public APIs used by this MCP.",
                "Create a top-level reminder instead, or omit parent_reminder_id.",
            )
        priority_value = _coerce_int_arg("priority", priority, minimum=0)
        list_title = _list_title(list_id)
        ensure_action_allowed("reminders_create_reminder", list_title)
        detail = _bridge().create_reminder(
            title=title.strip(),
            list_id=list_id,
            notes=notes,
            due_date=due_date,
            due_all_day=due_all_day,
            remind_at=remind_at,
            priority=priority_value,
            parent_reminder_id=parent_reminder_id,
            tags=tags,
        )
        return ReminderResponse(reminder=detail)
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except RemindersBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except ValueError as exc:
        return _error_response("INVALID_INPUT", str(exc), "Provide a non-empty title.")


@mcp.tool(
    title="Update Reminder",
    description="Update one or more fields on an existing reminder.",
    annotations=ToolAnnotations(destructive_hint=True, idempotent_hint=False, open_world_hint=False),
    structured_output=True,
)
def reminders_update_reminder(
    reminder_id: Annotated[str, Field(description=_REMINDER_ID_DESCRIPTION)],
    title: Annotated[str | None, Field(description=f"New title. {_OMIT_UNCHANGED}")] = None,
    list_id: Annotated[str | None, Field(description=f"Destination list to move the reminder to. {_LIST_ID_DESCRIPTION} {_OMIT_UNCHANGED}")] = None,
    notes: Annotated[str | None, Field(description=f"Replacement notes; overwrites the existing notes. {_OMIT_UNCHANGED}")] = None,
    due_date: Annotated[str | None, Field(description=f"New due date. {_DATE_FORMAT} {_OMIT_UNCHANGED}")] = None,
    due_all_day: Annotated[bool | None, Field(description=f"{_DUE_ALL_DAY_DESCRIPTION} Use together with due_date.")] = None,
    remind_at: Annotated[str | None, Field(description=f"New alert time; replaces the reminder's alerts. {_DATE_FORMAT} {_OMIT_UNCHANGED}")] = None,
    priority: Annotated[int | str | None, Field(description=f"{_PRIORITY_DESCRIPTION} {_OMIT_UNCHANGED}")] = None,
    parent_reminder_id: Annotated[str | None, Field(description=_PARENT_DESCRIPTION)] = None,
    tags: Annotated[
        list[str] | None,
        Field(description=f"{_TAGS_DESCRIPTION} Added to the existing notes (or to notes, if given); existing tags are not removed."),
    ] = None,
) -> ReminderResponse | ErrorResponse:
    try:
        if parent_reminder_id is not None:
            return _error_response(
                "SUBTASKS_UNSUPPORTED",
                "Apple Reminders subtasks are not available through the public APIs used by this MCP.",
                "Update the reminder without parent_reminder_id.",
            )
        ensure_action_allowed("reminders_update_reminder", _reminder_owner_list(reminder_id))
        if list_id is not None:
            ensure_action_allowed("reminders_update_reminder", _list_title(list_id))
        priority_value = _coerce_int_arg("priority", priority, minimum=0) if priority is not None else None
        detail = _bridge().update_reminder(
            reminder_id,
            title=title,
            list_id=list_id,
            notes=notes,
            due_date=due_date,
            due_all_day=due_all_day,
            remind_at=remind_at,
            priority=priority_value,
            parent_reminder_id=parent_reminder_id,
            tags=tags,
        )
        return ReminderResponse(reminder=detail)
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except RemindersBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Complete Reminder",
    description="Mark a reminder as completed.",
    annotations=ToolAnnotations(destructive_hint=True, idempotent_hint=True, open_world_hint=False),
    structured_output=True,
)
def reminders_complete_reminder(reminder_id: Annotated[str, Field(description=_REMINDER_ID_DESCRIPTION)]) -> ReminderResponse | ErrorResponse:
    try:
        ensure_action_allowed("reminders_complete_reminder", _reminder_owner_list(reminder_id))
        detail = _bridge().set_completed(reminder_id, True)
        return ReminderResponse(reminder=detail)
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except RemindersBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Uncomplete Reminder",
    description="Mark a reminder as not completed.",
    annotations=ToolAnnotations(destructive_hint=True, idempotent_hint=True, open_world_hint=False),
    structured_output=True,
)
def reminders_uncomplete_reminder(reminder_id: Annotated[str, Field(description=_REMINDER_ID_DESCRIPTION)]) -> ReminderResponse | ErrorResponse:
    try:
        ensure_action_allowed("reminders_uncomplete_reminder", _reminder_owner_list(reminder_id))
        detail = _bridge().set_completed(reminder_id, False)
        return ReminderResponse(reminder=detail)
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except RemindersBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Delete Reminder",
    description="Delete a reminder by reminder_id.",
    annotations=ToolAnnotations(destructive_hint=True, idempotent_hint=False, open_world_hint=False),
    structured_output=True,
)
def reminders_delete_reminder(reminder_id: Annotated[str, Field(description=_REMINDER_ID_DESCRIPTION)]) -> DeleteReminderResponse | ErrorResponse:
    try:
        ensure_action_allowed("reminders_delete_reminder", _reminder_owner_list(reminder_id))
        deleted = _bridge().delete_reminder(reminder_id)
        return DeleteReminderResponse(deleted=deleted, reminder_id=reminder_id)
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except RemindersBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


def _serialize_prompt_messages(messages: list[PromptMessage]) -> list[dict[str, object]]:
    return [
        {
            "role": getattr(message, "role", "user"),
            "content": message.content.model_dump(mode="json") if hasattr(message.content, "model_dump") else message.content,
        }
        for message in messages
    ]


@mcp.tool(
    title="Reminders List Prompts",
    description="Fallback prompt discovery tool for tool-only MCP clients.",
    annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
    structured_output=True,
)
async def reminders_list_prompts() -> dict[str, object]:
    prompts = await mcp.list_prompts()
    return {
        "ok": True,
        "prompts": [{"name": prompt.name, "title": prompt.title, "description": prompt.description} for prompt in prompts],
        "count": len(prompts),
    }


@mcp.tool(
    title="Reminders Get Prompt",
    description="Fallback prompt rendering tool for tool-only MCP clients.",
    annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
    structured_output=True,
)
async def reminders_get_prompt(
    name: Annotated[str, Field(description=_PROMPT_NAME_DESCRIPTION)],
    arguments_json: Annotated[str | None, Field(description=_PROMPT_ARGUMENTS_DESCRIPTION)] = None,
) -> dict[str, object]:
    arguments = json.loads(arguments_json) if arguments_json else None
    prompt = await mcp.get_prompt(name, arguments)
    if isinstance(prompt, InputRequiredResult):
        return {"ok": False, "name": name, "error": {"error_code": "PROMPT_INPUT_REQUIRED", "message": f"Prompt '{name}' needs client input before it can render."}}
    return {"ok": True, "name": name, "messages": _serialize_prompt_messages(prompt.messages), "message_count": len(prompt.messages)}


TOOL_DISCOVERY = install_search_first_discovery(
    mcp,
    server_name="Apple Reminders MCP",
    domain="reminders",
)


def main() -> None:
    transport = os.environ.get("APPLE_REMINDERS_MCP_TRANSPORT", "stdio")
    if transport == "streamable-http":
        mcp.run(
            transport="streamable-http",
            host=require_loopback_host(os.environ.get("APPLE_REMINDERS_MCP_HOST", "127.0.0.1")),
            port=int(os.environ.get("APPLE_REMINDERS_MCP_PORT", "8738")),
            json_response=True,
            stateless_http=False,
        )
        return
    mcp.run(transport="stdio")
