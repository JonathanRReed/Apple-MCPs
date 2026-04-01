from typing import Any, Literal

from pydantic import BaseModel, Field


class AppleHealthResponse(BaseModel):
    ok: Literal[True] = True
    server_name: str
    version: str
    transport: str
    domains: dict[str, dict[str, Any]]


class AppleOverviewResponse(BaseModel):
    ok: Literal[True] = True
    overview: dict[str, Any]


class PermissionGuideResponse(BaseModel):
    ok: Literal[True] = True
    domain: str
    can_prompt_in_app: bool
    requires_manual_system_settings: bool
    steps: list[str]
    notes: list[str]


class SuggestionListResponse(BaseModel):
    ok: Literal[True] = True
    domain: str
    suggestions: list[str]
    count: int


class AppleToolError(BaseModel):
    error_code: str
    message: str
    suggestion: str | None = None


class AppleErrorResponse(BaseModel):
    ok: Literal[False] = False
    error: AppleToolError


class ContactRoutingPreference(BaseModel):
    preferred_communication_channel: Literal["auto", "messages", "mail"] = "auto"
    preferred_message_channel: Literal["auto", "phone", "email"] = "auto"
    preferred_mail_address: str | None = None
    preferred_message_target: str | None = None


class AssistantPreferences(BaseModel):
    default_mail_account: str | None = None
    default_archive_mailbox: str | None = None
    default_archive_account: str | None = None
    default_calendar_id: str | None = None
    default_calendar_name: str | None = None
    default_reminder_list_id: str | None = None
    default_reminder_list_name: str | None = None
    default_notes_folder_id: str | None = None
    default_notes_folder_name: str | None = None
    default_notes_account_name: str | None = None
    preferred_communication_channel: Literal["auto", "messages", "mail"] = "auto"
    preferred_message_channel: Literal["auto", "phone", "email"] = "auto"
    contact_preferences: dict[str, ContactRoutingPreference] = Field(default_factory=dict)


class PreferencesResponse(BaseModel):
    ok: Literal[True] = True
    preferences: AssistantPreferences


class PreferencesDetectResponse(BaseModel):
    ok: Literal[True] = True
    preferences: AssistantPreferences
    detected: list[str]
    count: int


class CommunicationPlanResponse(BaseModel):
    ok: Literal[True] = True
    recipient_query: str
    resolved_contact_id: str | None = None
    resolved_contact_name: str | None = None
    channels_available: list[str] = Field(default_factory=list)
    recommended_channel: Literal["messages", "mail"]
    recommended_target: str
    rationale: str


class CommunicationActionResponse(BaseModel):
    ok: Literal[True] = True
    channel: Literal["messages", "mail"]
    target: str
    action_id: str | None = None
    result: dict[str, Any]


class MailFollowupResponse(BaseModel):
    ok: Literal[True] = True
    message_id: str
    reminder: dict[str, Any] | None = None
    note: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)


class EventCollaborationResponse(BaseModel):
    ok: Literal[True] = True
    event_id: str
    title: str
    calendar_name: str
    attendee_count: int
    accepted_count: int
    tentative_count: int
    declined_count: int
    pending_count: int
    attendees: list[dict[str, Any]] = Field(default_factory=list)


class ActionPreviewResponse(BaseModel):
    ok: Literal[True] = True
    action_type: str
    summary: str
    execution_tool: str
    execution_arguments: dict[str, Any]
    undo_supported: bool = False
    warnings: list[str] = Field(default_factory=list)


class AssistantActionRecord(BaseModel):
    action_id: str
    action_type: str
    created_at: str
    summary: str
    undo_supported: bool = False
    undo_status: Literal["available", "not_supported", "undone", "failed"] = "available"
    undo_tool: str | None = None
    undo_arguments: dict[str, Any] | None = None
    result: dict[str, Any] = Field(default_factory=dict)


class ActionHistoryResponse(BaseModel):
    ok: Literal[True] = True
    actions: list[AssistantActionRecord]
    count: int


class ActionUndoResponse(BaseModel):
    ok: Literal[True] = True
    action: AssistantActionRecord
    undo_result: dict[str, Any] | None = None
