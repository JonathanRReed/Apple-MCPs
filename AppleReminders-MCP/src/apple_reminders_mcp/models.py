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


class ReminderListInfo(BaseModel):
    list_id: str
    title: str
    source_title: str | None = None
    allows_content_modifications: bool
    color_hex: str | None = None


class ReminderListResponse(BaseModel):
    ok: Literal[True] = True
    lists: list[ReminderListInfo]
    count: int


class ReminderSummary(BaseModel):
    reminder_id: str
    title: str
    list_id: str
    list_name: str
    due_date: str | None = None
    due_all_day: bool = False
    remind_at: str | None = None
    priority: int = 0
    completed: bool = False
    completion_date: str | None = None
    tags: list[str] = Field(default_factory=list)
    subtask_ids: list[str] = Field(default_factory=list)


class ReminderDetail(ReminderSummary):
    notes: str | None = None
    creation_date: str | None = None
    modification_date: str | None = None


class ReminderListItemsResponse(BaseModel):
    ok: Literal[True] = True
    reminders: list[ReminderSummary]
    count: int


class ReminderResponse(BaseModel):
    ok: Literal[True] = True
    reminder: ReminderDetail


class DeleteReminderResponse(BaseModel):
    ok: Literal[True] = True
    deleted: bool
    reminder_id: str


class ReminderListMutationResponse(BaseModel):
    ok: Literal[True] = True
    list_id: str
    title: str
    created: bool = True


class DeleteReminderListResponse(BaseModel):
    ok: Literal[True] = True
    deleted: bool
    list_id: str
