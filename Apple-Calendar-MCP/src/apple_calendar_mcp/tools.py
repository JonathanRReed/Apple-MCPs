import json

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import Annotations, ToolAnnotations

from apple_calendar_mcp.calendar_bridge import CalendarBridge, CalendarBridgeError
from apple_calendar_mcp.config import load_settings
from apple_calendar_mcp.models import CalendarListResponse, DeleteEventResponse, ErrorResponse, EventListResponse, EventResponse, HealthResponse, ToolError
from apple_calendar_mcp.permissions import SafetyError, ensure_action_allowed
from apple_calendar_mcp.utils import parse_iso_datetime

SERVER_INSTRUCTIONS = (
    "Use this server for Apple Calendar on macOS. "
    "Search here when the user wants to review calendar availability, inspect events, create events, edit events, or delete events. "
    "Prefer list and get tools before mutations when ids or calendar ids are unknown."
)

mcp = FastMCP("Apple Calendar", instructions=SERVER_INSTRUCTIONS, json_response=True)


def _bridge() -> CalendarBridge:
    settings = load_settings()
    return CalendarBridge(settings.helper_source, settings.helper_binary)


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
            "list_calendars",
            "list_events",
            "get_event",
            "create_event",
            "update_event",
            "delete_event",
            "resources",
            "prompts",
        ],
        source_exists,
        binary_exists,
    )


def _validate_time_window(start_iso: str, end_iso: str) -> tuple[str, str]:
    start = parse_iso_datetime(start_iso)
    end = parse_iso_datetime(end_iso)
    if end <= start:
        raise ValueError("end_iso must be later than start_iso")
    return start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")


def _calendar_name_from_id(calendar_id: str | None) -> str | None:
    if calendar_id is None:
        return None
    for calendar in _bridge().list_calendars():
        if calendar.calendar_id == calendar_id:
            return calendar.name
    return None


def _event_owner_calendar(event_id: str) -> str | None:
    return _bridge().get_event(event_id).calendar_name


@mcp.resource(
    "calendar://calendars",
    name="calendar_list_snapshot",
    title="Calendar List",
    description="Current Apple Calendar calendars.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.9),
)
def calendar_calendars_resource() -> str:
    calendars = _bridge().list_calendars()
    return _resource_json({"calendars": [item.model_dump() for item in calendars], "count": len(calendars)})


@mcp.resource(
    "calendar://events/today",
    name="calendar_today_snapshot",
    title="Today's Events",
    description="A compact snapshot of today's Apple Calendar events.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.8),
)
def calendar_events_today_resource() -> str:
    from datetime import datetime, timedelta

    now = datetime.now().astimezone()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    events = _bridge().list_events(start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds"), limit=50)
    return _resource_json({"events": [item.model_dump() for item in events], "count": len(events)})


@mcp.prompt(name="calendar_plan_today", title="Plan Today")
def calendar_plan_today_prompt() -> str:
    return (
        "Review today's Apple Calendar events, summarize the schedule, identify conflicts or gaps, "
        "and suggest a practical plan for the day. Start by listing today's events."
    )


@mcp.prompt(name="calendar_prepare_agenda", title="Prepare Agenda")
def calendar_prepare_agenda_prompt() -> str:
    return (
        "Use Apple Calendar to review upcoming events and prepare a concise agenda or briefing. "
        "List relevant events first, then inspect individual event details when needed."
    )


@mcp.tool(
    title="Calendar Health",
    description="Report the active Apple Calendar server configuration.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def calendar_health() -> HealthResponse:
    settings = load_settings()
    capabilities, helper_available, helper_compiled = _capabilities()
    access_status = "helper_unavailable"
    can_read_events = False
    can_write_events = False
    permission_error = None
    permission_suggestion = None
    if helper_available:
        try:
            access_payload = _bridge().calendar_access_status()
            access_status = str(access_payload.get("status", "unknown"))
            can_read_events = bool(access_payload.get("can_read_events", False))
            can_write_events = bool(access_payload.get("can_write_events", False))
            if not can_read_events:
                permission_error = access_payload.get("message")
                permission_suggestion = access_payload.get("suggestion")
        except CalendarBridgeError as exc:
            access_status = "helper_error"
            permission_error = exc.message
            permission_suggestion = exc.suggestion
    if not can_read_events:
        try:
            _bridge().list_calendars()
            access_status = "applescript_fallback"
            can_read_events = True
            permission_error = None
            permission_suggestion = None
        except CalendarBridgeError:
            pass
    return HealthResponse(
        server_name=settings.server_name,
        version=settings.version,
        safety_mode=settings.safety_mode,
        capabilities=capabilities,
        helper_available=helper_available,
        helper_compiled=helper_compiled,
        access_status=access_status,
        can_read_events=can_read_events,
        can_write_events=can_write_events,
        permission_error=permission_error,
        permission_suggestion=permission_suggestion,
    )


@mcp.tool(
    title="Calendar Permission Guide",
    description="Explain how to grant Apple Calendar permission on macOS.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def calendar_permission_guide() -> dict[str, object]:
    return {
        "ok": True,
        "domain": "calendar",
        "can_prompt_in_app": True,
        "requires_manual_system_settings": False,
        "steps": [
            "Call a Calendar tool from this MCP server.",
            "Approve the macOS Calendar access prompt when it appears.",
            "If access was denied before, re-enable it in System Settings > Privacy & Security > Calendars.",
        ],
    }


@mcp.tool(
    title="Calendar Recheck Permissions",
    description="Recheck Calendar access after the user changes macOS permissions, and notify the client that Calendar resources changed.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=False),
    structured_output=True,
)
async def calendar_recheck_permissions(ctx: Context) -> HealthResponse:
    await ctx.report_progress(25, 100, "Rechecking Calendar access")
    response = calendar_health()
    await ctx.session.send_resource_list_changed()
    await ctx.report_progress(100, 100, "Done")
    return response


@mcp.tool(
    title="List Calendars",
    description="List available Apple Calendar calendars.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def calendar_list_calendars() -> CalendarListResponse | ErrorResponse:
    try:
        ensure_action_allowed("calendar_list_calendars")
        calendars = _bridge().list_calendars()
        return CalendarListResponse(calendars=calendars, count=len(calendars))
    except (SafetyError, CalendarBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="List Events",
    description="List calendar events in a time window, optionally filtered to one calendar.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def calendar_list_events(start_iso: str, end_iso: str, calendar_id: str | None = None, limit: int | str = 100) -> EventListResponse | ErrorResponse:
    try:
        limit_value = _coerce_int_arg("limit", limit, minimum=1)
        ensure_action_allowed("calendar_list_events", _calendar_name_from_id(calendar_id))
        start_value, end_value = _validate_time_window(start_iso, end_iso)
        events = _bridge().list_events(start_value, end_value, calendar_id=calendar_id, limit=limit_value)
        return EventListResponse(events=events, count=len(events))
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except CalendarBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except ValueError as exc:
        return _error_response("INVALID_INPUT", str(exc), "Provide valid ISO datetimes and a positive limit.")


@mcp.tool(
    title="Get Event",
    description="Fetch full details for a calendar event by event_id.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def calendar_get_event(event_id: str) -> EventResponse | ErrorResponse:
    try:
        ensure_action_allowed("calendar_get_event", _event_owner_calendar(event_id))
        event = _bridge().get_event(event_id)
        return EventResponse(event=event)
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except CalendarBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Create Event",
    description="Create a new event in a specific Apple Calendar calendar.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def calendar_create_event(
    title: str,
    start_iso: str,
    end_iso: str,
    calendar_id: str,
    notes: str | None = None,
    location: str | None = None,
    all_day: bool = False,
    recurrence: dict[str, object] | None = None,
) -> EventResponse | ErrorResponse:
    try:
        if not title.strip():
            raise ValueError("title must not be empty")
        ensure_action_allowed("calendar_create_event", _calendar_name_from_id(calendar_id))
        start_value, end_value = _validate_time_window(start_iso, end_iso)
        event = _bridge().create_event(
            title=title.strip(),
            calendar_id=calendar_id,
            start_iso=start_value,
            end_iso=end_value,
            notes=notes,
            location=location,
            all_day=all_day,
            recurrence=recurrence,
        )
        return EventResponse(event=event)
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except CalendarBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except ValueError as exc:
        return _error_response("INVALID_INPUT", str(exc), "Provide a non-empty title and valid ISO datetimes.")


@mcp.tool(
    title="Update Event",
    description="Update one or more fields on an existing calendar event.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def calendar_update_event(
    event_id: str,
    title: str | None = None,
    start_iso: str | None = None,
    end_iso: str | None = None,
    calendar_id: str | None = None,
    notes: str | None = None,
    location: str | None = None,
    all_day: bool | None = None,
    recurrence: dict[str, object] | None = None,
) -> EventResponse | ErrorResponse:
    try:
        ensure_action_allowed("calendar_update_event", _event_owner_calendar(event_id))
        event = _bridge().update_event(
            event_id,
            title=title,
            start_iso=start_iso,
            end_iso=end_iso,
            calendar_id=calendar_id,
            notes=notes,
            location=location,
            all_day=all_day,
            recurrence=recurrence,
        )
        return EventResponse(event=event)
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except CalendarBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Delete Event",
    description="Delete a calendar event by event_id.",
    annotations=ToolAnnotations(destructiveHint=True, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def calendar_delete_event(event_id: str) -> DeleteEventResponse | ErrorResponse:
    try:
        ensure_action_allowed("calendar_delete_event", _event_owner_calendar(event_id))
        deleted = _bridge().delete_event(event_id)
        return DeleteEventResponse(deleted=deleted, event_id=event_id)
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except CalendarBridgeError as exc:
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
    title="Calendar List Prompts",
    description="Fallback prompt discovery tool for tool-only MCP clients.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
async def calendar_list_prompts() -> dict[str, object]:
    prompts = await mcp.list_prompts()
    return {
        "ok": True,
        "prompts": [{"name": prompt.name, "title": prompt.title, "description": prompt.description} for prompt in prompts],
        "count": len(prompts),
    }


@mcp.tool(
    title="Calendar Get Prompt",
    description="Fallback prompt rendering tool for tool-only MCP clients.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
async def calendar_get_prompt(name: str, arguments_json: str | None = None) -> dict[str, object]:
    arguments = json.loads(arguments_json) if arguments_json else None
    prompt = await mcp.get_prompt(name, arguments)
    return {"ok": True, "name": name, "messages": _serialize_prompt_messages(prompt.messages), "message_count": len(prompt.messages)}


@mcp._mcp_server.subscribe_resource()
async def _calendar_subscribe_resource(uri) -> None:
    del uri


@mcp._mcp_server.unsubscribe_resource()
async def _calendar_unsubscribe_resource(uri) -> None:
    del uri


def main() -> None:
    mcp.run(transport="stdio")
