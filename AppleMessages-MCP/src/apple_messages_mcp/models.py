from typing import Literal

from pydantic import BaseModel, Field


class ToolError(BaseModel):
    error_code: str = Field(description="Stable machine-readable error code")
    message: str = Field(description="Human-readable error message")
    suggestion: str | None = Field(default=None, description="Suggested next step")


class ErrorResponse(BaseModel):
    ok: Literal[False] = False
    error: ToolError


class MessagesCapabilities(BaseModel):
    can_read_history: bool
    can_send_messages: bool
    can_reply_in_existing_chat: bool
    requires_full_disk_access: bool = True
    requires_messages_automation: bool = True


class HealthResponse(BaseModel):
    ok: Literal[True] = True
    server_name: str
    version: str
    safety_mode: str
    capabilities: MessagesCapabilities
    history_access: bool
    automation_access: bool
    history_access_error: str | None = None
    history_access_suggestion: str | None = None
    automation_access_error: str | None = None
    automation_access_suggestion: str | None = None
    transport: str


class ParticipantRecord(BaseModel):
    handle_id: str
    address: str
    service: str | None = None
    uncanonicalized_address: str | None = None


class AttachmentRecord(BaseModel):
    attachment_id: str
    message_id: str
    path: str | None = None
    transfer_name: str | None = None
    mime_type: str | None = None


class MessageRecord(BaseModel):
    message_id: str
    guid: str | None = None
    chat_id: str | None = None
    sender: ParticipantRecord | None = None
    text: str | None = None
    subject: str | None = None
    service_name: str | None = None
    sent_at: str | None = None
    is_from_me: bool
    has_attachments: bool = False


class ConversationSummary(BaseModel):
    chat_id: str
    guid: str | None = None
    display_name: str | None = None
    service_name: str | None = None
    participants: list[ParticipantRecord]
    unread_count: int = 0
    last_activity_at: str | None = None
    last_message_preview: str | None = None


class ConversationRecord(ConversationSummary):
    messages: list[MessageRecord]


class ConversationListResponse(BaseModel):
    ok: Literal[True] = True
    conversations: list[ConversationSummary]
    count: int


class ConversationResponse(BaseModel):
    ok: Literal[True] = True
    conversation: ConversationRecord


class MessageResponse(BaseModel):
    ok: Literal[True] = True
    message: MessageRecord


class MessageSearchResponse(BaseModel):
    ok: Literal[True] = True
    messages: list[MessageRecord]
    count: int


class AttachmentListResponse(BaseModel):
    ok: Literal[True] = True
    attachments: list[AttachmentRecord]
    count: int


class SendResponse(BaseModel):
    ok: Literal[True] = True
    sent: bool
    recipient: str | None = None
    chat_id: str | None = None
    file_path: str | None = None
    text: str | None = None
    service_name: str | None = None
