from typing import Literal

from pydantic import BaseModel, Field


class ToolError(BaseModel):
    error_code: str = Field(description="Stable machine-readable error code")
    message: str = Field(description="Human-readable error message")
    suggestion: str | None = Field(default=None, description="Suggested next step")


class ErrorResponse(BaseModel):
    ok: Literal[False] = False
    error: ToolError


class HealthResponse(BaseModel):
    ok: Literal[True] = True
    server_name: str
    version: str
    safety_mode: str
    transport: str = "stdio"
    capabilities: list[str]
    helper_available: bool
    helper_compiled: bool
    access_status: str
    can_read_events: bool
    can_write_events: bool
    permission_error: str | None = None
    permission_suggestion: str | None = None


class CalendarInfo(BaseModel):
    calendar_id: str
    name: str
    source_title: str | None = None
    color_hex: str | None = None
    writable: bool | None = None


class CalendarListResponse(BaseModel):
    ok: Literal[True] = True
    calendars: list[CalendarInfo]
    count: int


class EventSummary(BaseModel):
    event_id: str
    title: str
    calendar_id: str
    calendar_name: str
    start: str
    end: str
    all_day: bool
    location: str | None = None
    availability: str | None = None


class EventDetail(EventSummary):
    notes: str | None = None


class EventListResponse(BaseModel):
    ok: Literal[True] = True
    events: list[EventSummary]
    count: int


class EventResponse(BaseModel):
    ok: Literal[True] = True
    event: EventDetail


class DeleteEventResponse(BaseModel):
    ok: Literal[True] = True
    deleted: bool
    event_id: str


class UpdateEventResponse(BaseModel):
    ok: Literal[True] = True
    event: EventDetail
