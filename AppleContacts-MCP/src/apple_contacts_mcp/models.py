from typing import Literal

from pydantic import BaseModel, Field


class ToolError(BaseModel):
    error_code: str = Field(description="Stable machine-readable error code")
    message: str = Field(description="Human-readable error message")
    suggestion: str | None = Field(default=None, description="Suggested next step")


class ErrorResponse(BaseModel):
    ok: Literal[False] = False
    error: ToolError


class ContactMethod(BaseModel):
    label: str
    value: str


class ContactSummary(BaseModel):
    contact_id: str
    name: str
    first_name: str = ""
    last_name: str = ""
    organization: str = ""
    phone_count: int = 0
    email_count: int = 0
    phones: list[ContactMethod] = Field(default_factory=list)
    emails: list[ContactMethod] = Field(default_factory=list)


class ContactDetail(ContactSummary):
    note: str = ""


class HealthResponse(BaseModel):
    ok: Literal[True] = True
    server_name: str
    version: str
    safety_mode: str
    transport: str = "stdio"
    capabilities: list[str]
    contacts_accessible: bool
    permission_error: str | None = None
    permission_suggestion: str | None = None


class ContactListResponse(BaseModel):
    ok: Literal[True] = True
    contacts: list[ContactSummary]
    count: int


class ContactResponse(BaseModel):
    ok: Literal[True] = True
    contact: ContactDetail


class ResolvedRecipientResponse(BaseModel):
    ok: Literal[True] = True
    contact: ContactDetail
    recipient_kind: Literal["phone", "email"]
    recipient_label: str
    recipient_value: str
