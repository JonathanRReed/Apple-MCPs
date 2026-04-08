from __future__ import annotations

import json

from apple_mcp_common.discovery import install_search_first_discovery
from mcp.server.fastmcp import Context, FastMCP
from mcp.types import Annotations, ToolAnnotations

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

mcp = FastMCP("Apple Reminders MCP", instructions=SERVER_INSTRUCTIONS, json_response=True)


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


@mcp.resource(
    "reminders://lists",
    name="reminder_lists",
    title="Reminder Lists",
    description="Current Apple Reminders lists.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.9),
)
def reminders_lists_resource() -> str:
    lists = _bridge().list_lists()
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
    reminders = _bridge().list_reminders(include_completed=False, limit=25)
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
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
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
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
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
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=False),
    structured_output=True,
)
async def reminders_recheck_permissions(ctx: Context) -> HealthResponse:
    await ctx.report_progress(25, 100, "Rechecking Reminders access")
    response = reminders_health()
    await ctx.session.send_resource_list_changed()
    await ctx.report_progress(100, 100, "Done")
    return response


@mcp.tool(
    title="List Reminder Lists",
    description="List available Apple Reminders lists.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def reminders_list_lists() -> ReminderListResponse | ErrorResponse:
    try:
        ensure_action_allowed("reminders_list_lists")
        lists = _bridge().list_lists()
        return ReminderListResponse(lists=lists, count=len(lists))
    except (SafetyError, RemindersBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Create Reminder List",
    description="Create a new Apple Reminders list.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def reminders_create_list(title: str) -> ReminderListMutationResponse | ErrorResponse:
    if not title.strip():
        return _error_response("INVALID_INPUT", "title must not be empty", "Provide a non-empty title.")
    try:
        ensure_action_allowed("reminders_create_list")
        return _bridge().create_list(title=title.strip())
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except RemindersBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Delete Reminder List",
    description="Delete a reminder list entirely. Requires full_access safety mode.",
    annotations=ToolAnnotations(destructiveHint=True, idempotentHint=True, openWorldHint=False),
    structured_output=True,
)
def reminders_delete_list(list_id: str) -> DeleteReminderListResponse | ErrorResponse:
    try:
        ensure_action_allowed("reminders_delete_list")
        return _bridge().delete_list(list_id=list_id)
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except RemindersBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="List Reminders",
    description="List reminders with optional list and due-date filters.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def reminders_list_reminders(
    list_id: str | None = None,
    include_completed: bool = True,
    limit: int | str = 100,
    search: str | None = None,
    due_after: str | None = None,
    due_before: str | None = None,
) -> ReminderListItemsResponse | ErrorResponse:
    try:
        limit_value = _coerce_int_arg("limit", limit, minimum=1)
        list_name = None
        if list_id is not None:
            for list_info in _bridge().list_lists():
                if list_info.list_id == list_id:
                    list_name = list_info.title
                    break
        ensure_action_allowed("reminders_list_reminders", list_name)
        reminders = _bridge().list_reminders(
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
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def reminders_get_reminder(reminder_id: str) -> ReminderResponse | ErrorResponse:
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
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def reminders_create_reminder(
    title: str,
    list_id: str,
    notes: str | None = None,
    due_date: str | None = None,
    due_all_day: bool = False,
    remind_at: str | None = None,
    priority: int | str = 0,
    parent_reminder_id: str | None = None,
    tags: list[str] | None = None,
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
        list_title = None
        for list_info in _bridge().list_lists():
            if list_info.list_id == list_id:
                list_title = list_info.title
                break
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
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def reminders_update_reminder(
    reminder_id: str,
    title: str | None = None,
    list_id: str | None = None,
    notes: str | None = None,
    due_date: str | None = None,
    due_all_day: bool | None = None,
    remind_at: str | None = None,
    priority: int | str | None = None,
    parent_reminder_id: str | None = None,
    tags: list[str] | None = None,
) -> ReminderResponse | ErrorResponse:
    try:
        if parent_reminder_id is not None:
            return _error_response(
                "SUBTASKS_UNSUPPORTED",
                "Apple Reminders subtasks are not available through the public APIs used by this MCP.",
                "Update the reminder without parent_reminder_id.",
            )
        ensure_action_allowed("reminders_update_reminder", _reminder_owner_list(reminder_id))
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
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=True, openWorldHint=False),
    structured_output=True,
)
def reminders_complete_reminder(reminder_id: str) -> ReminderResponse | ErrorResponse:
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
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=True, openWorldHint=False),
    structured_output=True,
)
def reminders_uncomplete_reminder(reminder_id: str) -> ReminderResponse | ErrorResponse:
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
    annotations=ToolAnnotations(destructiveHint=True, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def reminders_delete_reminder(reminder_id: str) -> DeleteReminderResponse | ErrorResponse:
    try:
        ensure_action_allowed("reminders_delete_reminder", _reminder_owner_list(reminder_id))
        deleted = _bridge().delete_reminder(reminder_id)
        return DeleteReminderResponse(deleted=deleted, reminder_id=reminder_id)
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except RemindersBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


def _serialize_prompt_messages(messages: list[object]) -> list[dict[str, object]]:
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
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
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
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
async def reminders_get_prompt(name: str, arguments_json: str | None = None) -> dict[str, object]:
    arguments = json.loads(arguments_json) if arguments_json else None
    prompt = await mcp.get_prompt(name, arguments)
    return {"ok": True, "name": name, "messages": _serialize_prompt_messages(prompt.messages), "message_count": len(prompt.messages)}


@mcp._mcp_server.subscribe_resource()
async def _reminders_subscribe_resource(uri) -> None:
    del uri


@mcp._mcp_server.unsubscribe_resource()
async def _reminders_unsubscribe_resource(uri) -> None:
    del uri


TOOL_DISCOVERY = install_search_first_discovery(
    mcp,
    server_name="Apple Reminders MCP",
    domain="reminders",
)


def main() -> None:
    mcp.run(transport="stdio")
