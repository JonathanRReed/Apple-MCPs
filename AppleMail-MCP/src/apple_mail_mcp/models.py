from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SafetyProfile(str, Enum):
    SAFE_READONLY = "safe_readonly"
    SAFE_MANAGE = "safe_manage"
    FULL_ACCESS = "full_access"


@dataclass
class MailboxRecord:
    account: str
    name: str

    def to_dict(self) -> dict[str, str]:
        return {
            "account": self.account,
            "name": self.name,
        }


@dataclass
class AttachmentRecord:
    name: str
    mime_type: str | None = None
    size_bytes: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
        }


@dataclass
class MessageSummary:
    message_id: str
    subject: str
    sender: str
    date_received: str
    mailbox: str
    account: str
    is_read: bool
    preview: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "subject": self.subject,
            "sender": self.sender,
            "date_received": self.date_received,
            "mailbox": self.mailbox,
            "account": self.account,
            "is_read": self.is_read,
            "preview": self.preview,
        }


@dataclass
class MessageRecord(MessageSummary):
    to: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)
    body_text: str = ""
    attachments: list[AttachmentRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result.update(
            {
                "to": self.to,
                "cc": self.cc,
                "body_text": self.body_text,
                "attachments": [attachment.to_dict() for attachment in self.attachments],
            }
        )
        return result


@dataclass
class DraftRecord:
    draft_id: str
    subject: str
    to: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    visible: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "draft_id": self.draft_id,
            "subject": self.subject,
            "to": self.to,
            "cc": self.cc,
            "bcc": self.bcc,
            "visible": self.visible,
        }


@dataclass
class SendRecord:
    subject: str
    to: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    sent: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "to": self.to,
            "cc": self.cc,
            "bcc": self.bcc,
            "sent": self.sent,
        }


@dataclass
class HealthResponse:
    ok: bool
    server_name: str
    version: str
    safety_profile: str
    transport: str
    visible_drafts: bool
    capabilities: list[str] = field(default_factory=list)
    supports: list[str] = field(default_factory=list)


@dataclass
class MailboxListResponse:
    mailboxes: list[MailboxRecord] = field(default_factory=list)
    count: int = 0


@dataclass
class MessageSearchResponse:
    results: list[MessageSummary] = field(default_factory=list)
    count: int = 0


@dataclass
class ErrorResponse:
    ok: bool
    error_code: str
    message: str


def error_response(error_code: str, message: str) -> ErrorResponse:
    return ErrorResponse(
        ok=False,
        error_code=error_code,
        message=message,
    )
