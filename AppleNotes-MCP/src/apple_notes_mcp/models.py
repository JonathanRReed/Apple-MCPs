from typing import Literal

from pydantic import BaseModel, Field


class ToolError(BaseModel):
    error_code: str = Field(description="Stable machine-readable error code")
    message: str = Field(description="Human-readable error message")
    suggestion: str | None = Field(default=None, description="Suggested next step")


class ErrorResponse(BaseModel):
    ok: Literal[False] = False
    error: ToolError


class NotesCapabilities(BaseModel):
    supports_locked_notes: bool = False
    supports_shared_notes: bool = True
    supports_attachments: bool = True
    supports_ui_automation_fallback: bool = False


class HealthResponse(BaseModel):
    ok: Literal[True] = True
    server_name: str
    version: str
    safety_mode: str
    transport: str = "stdio"
    capabilities: NotesCapabilities


class AccountInfo(BaseModel):
    account_id: str
    name: str
    upgraded: bool | None = None
    default_folder_id: str | None = None


class FolderInfo(BaseModel):
    folder_id: str
    name: str
    account_id: str
    account_name: str
    parent_folder_id: str | None = None
    parent_folder_name: str | None = None
    shared: bool | None = None


class AttachmentInfo(BaseModel):
    name: str
    file_name: str | None = None


class NoteCapabilities(BaseModel):
    supports_locked_notes: bool = False
    supports_shared_notes: bool = True
    supports_attachments: bool = True
    supports_ui_automation_fallback: bool = False


class NoteSummary(BaseModel):
    note_id: str
    title: str
    account_id: str
    account_name: str
    folder_id: str
    folder_name: str
    created_epoch: int | None = None
    modified_epoch: int | None = None
    password_protected: bool = False
    shared: bool = False
    tags: list[str] = Field(default_factory=list)
    plaintext: str = ""
    preview: str = ""
    attachment_count: int = 0
    capabilities: NoteCapabilities = Field(default_factory=NoteCapabilities)


class NoteDetail(NoteSummary):
    body_html: str = ""
    attachments: list[AttachmentInfo] = Field(default_factory=list)


class AccountListResponse(BaseModel):
    ok: Literal[True] = True
    accounts: list[AccountInfo]
    count: int


class FolderListResponse(BaseModel):
    ok: Literal[True] = True
    folders: list[FolderInfo]
    count: int


class NoteListResponse(BaseModel):
    ok: Literal[True] = True
    notes: list[NoteSummary]
    count: int


class NoteResponse(BaseModel):
    ok: Literal[True] = True
    note: NoteDetail


class DeleteNoteResponse(BaseModel):
    ok: Literal[True] = True
    deleted: bool
    note_id: str


class MoveNoteResponse(BaseModel):
    ok: Literal[True] = True
    note: NoteDetail


class FolderMutationResponse(BaseModel):
    ok: Literal[True] = True
    folder: FolderInfo


class DeleteFolderResponse(BaseModel):
    ok: Literal[True] = True
    deleted: bool
    folder_id: str


class AttachmentListResponse(BaseModel):
    ok: Literal[True] = True
    attachments: list[AttachmentInfo]
    count: int
