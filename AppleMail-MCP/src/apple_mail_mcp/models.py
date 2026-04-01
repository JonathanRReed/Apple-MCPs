from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import re


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


def normalized_thread_subject(subject: str) -> str:
    cleaned = re.sub(r"^\s*((re|fw|fwd):\s*)+", "", subject or "", flags=re.IGNORECASE).strip()
    return cleaned or (subject or "").strip()


@dataclass
class DraftRecord:
    draft_id: str
    subject: str
    to: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    visible: bool = True
    from_account: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "draft_id": self.draft_id,
            "subject": self.subject,
            "to": self.to,
            "cc": self.cc,
            "bcc": self.bcc,
            "visible": self.visible,
            "from_account": self.from_account,
        }


@dataclass
class SendRecord:
    subject: str
    to: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    sent: bool = True
    from_account: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "to": self.to,
            "cc": self.cc,
            "bcc": self.bcc,
            "sent": self.sent,
            "from_account": self.from_account,
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


@dataclass
class ReplyRecord:
    sent: bool
    subject: str
    reply_all: bool = False
    from_account: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "sent": self.sent,
            "subject": self.subject,
            "reply_all": self.reply_all,
            "from_account": self.from_account,
        }


@dataclass
class ForwardRecord:
    sent: bool
    subject: str
    to: list[str] = field(default_factory=list)
    from_account: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "sent": self.sent,
            "subject": self.subject,
            "to": self.to,
            "from_account": self.from_account,
        }


@dataclass
class MarkRecord:
    message_id: str
    is_read: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "is_read": self.is_read,
        }


@dataclass
class MoveRecord:
    message_id: str
    moved: bool
    target_mailbox: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "moved": self.moved,
            "target_mailbox": self.target_mailbox,
        }


@dataclass
class DeleteRecord:
    message_id: str
    deleted: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "deleted": self.deleted,
        }


@dataclass
class ThreadRecord:
    message_id: str
    normalized_subject: str
    anchor_subject: str
    mailbox: str
    account: str
    messages: list[MessageSummary] = field(default_factory=list)
    count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "normalized_subject": self.normalized_subject,
            "anchor_subject": self.anchor_subject,
            "mailbox": self.mailbox,
            "account": self.account,
            "messages": [message.to_dict() for message in self.messages],
            "count": self.count,
        }


@dataclass
class ThreadMutationRecord:
    anchor_message_id: str
    normalized_subject: str
    affected_message_ids: list[str] = field(default_factory=list)
    count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "anchor_message_id": self.anchor_message_id,
            "normalized_subject": self.normalized_subject,
            "affected_message_ids": self.affected_message_ids,
            "count": self.count,
        }


def error_response(error_code: str, message: str) -> ErrorResponse:
    return ErrorResponse(
        ok=False,
        error_code=error_code,
        message=message,
    )
