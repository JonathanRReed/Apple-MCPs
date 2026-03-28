from __future__ import annotations

from importlib.resources import as_file, files
from pathlib import Path
from subprocess import run
from urllib.parse import quote, unquote

from apple_mail_mcp.models import AttachmentRecord, DraftRecord, MailboxRecord, MessageRecord, MessageSummary, SendRecord

FIELD_SEPARATOR = "\x1f"
LIST_SEPARATOR = "\x1d"
RECORD_SEPARATOR = "\x1e"


class MailBridgeError(Exception):
    pass


def encode_message_id(account: str, mailbox: str, apple_id: str) -> str:
    return "|".join(quote(part, safe="") for part in (account, mailbox, apple_id))


def decode_message_id(message_id: str) -> tuple[str, str, str]:
    parts = message_id.split("|")
    if len(parts) != 3:
        raise MailBridgeError(f"Invalid message_id: '{message_id}'.")
    return tuple(unquote(part) for part in parts)


def _restore_text(value: str) -> str:
    return value.replace("\\n", "\n")


def _parse_bool(value: str) -> bool:
    return value.strip().lower() == "true"


def _split_records(raw: str) -> list[list[str]]:
    if not raw:
        return []
    records: list[list[str]] = []
    for record in raw.split(RECORD_SEPARATOR):
        if not record:
            continue
        records.append(record.split(FIELD_SEPARATOR))
    return records


def _split_list(raw: str) -> list[str]:
    if not raw:
        return []
    return [_restore_text(item) for item in raw.split(LIST_SEPARATOR) if item]


class AppleMailBridge:
    def __init__(self, scripts_dir: Path | None = None) -> None:
        self.scripts_dir = scripts_dir

    def _run_script(self, script_name: str, args: list[str]) -> str:
        if self.scripts_dir is not None:
            script_path = self.scripts_dir / script_name
            if not script_path.exists():
                raise MailBridgeError(f"Script '{script_name}' was not found.")

            result = run(
                ["osascript", str(script_path), *args],
                capture_output=True,
                text=True,
                check=False,
            )
        else:
            bundled_script = files("apple_mail_mcp").joinpath("applescripts").joinpath(script_name)
            with as_file(bundled_script) as script_path:
                result = run(
                    ["osascript", str(script_path), *args],
                    capture_output=True,
                    text=True,
                    check=False,
                )
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or f"AppleScript '{script_name}' failed."
            raise MailBridgeError(message)
        return result.stdout.rstrip("\n\r")

    def list_mailboxes(self, account: str | None = None) -> list[MailboxRecord]:
        raw = self._run_script("list_mailboxes.applescript", [account or ""])
        return [
            MailboxRecord(account=_restore_text(row[0]), name=_restore_text(row[1]))
            for row in _split_records(raw)
            if len(row) >= 2
        ]

    def search_messages(
        self,
        query: str,
        mailbox: str | None = None,
        unread_only: bool = False,
        limit: int = 10,
    ) -> list[MessageSummary]:
        raw = self._run_script(
            "search_messages.applescript",
            [query, mailbox or "", "true" if unread_only else "false", str(limit)],
        )
        results: list[MessageSummary] = []
        for row in _split_records(raw):
            if len(row) < 8:
                continue
            account, mailbox_name, apple_id, subject, sender, date_received, is_read, preview = row[:8]
            results.append(
                MessageSummary(
                    message_id=encode_message_id(account, mailbox_name, apple_id),
                    subject=_restore_text(subject),
                    sender=_restore_text(sender),
                    date_received=_restore_text(date_received),
                    mailbox=_restore_text(mailbox_name),
                    account=_restore_text(account),
                    is_read=_parse_bool(is_read),
                    preview=_restore_text(preview),
                )
            )
        return results

    def get_message(self, message_id: str) -> MessageRecord:
        account, mailbox, apple_id = decode_message_id(message_id)
        raw = self._run_script("get_message.applescript", [account, mailbox, apple_id])
        rows = _split_records(raw)
        if not rows:
            raise MailBridgeError(f"Message '{message_id}' was not found.")

        row = rows[0]
        if len(row) < 11:
            raise MailBridgeError("Message payload was incomplete.")

        account_name, mailbox_name, apple_id, subject, sender, to_raw, cc_raw, date_received, is_read, body_text, attachments_raw = row[:11]
        restored_body_text = _restore_text(body_text)
        attachments = [AttachmentRecord(name=name) for name in _split_list(attachments_raw)]
        return MessageRecord(
            message_id=encode_message_id(account_name, mailbox_name, apple_id),
            subject=_restore_text(subject),
            sender=_restore_text(sender),
            date_received=_restore_text(date_received),
            mailbox=_restore_text(mailbox_name),
            account=_restore_text(account_name),
            is_read=_parse_bool(is_read),
            preview=restored_body_text[:240],
            to=_split_list(to_raw),
            cc=_split_list(cc_raw),
            body_text=restored_body_text,
            attachments=attachments,
        )

    def compose_draft(
        self,
        to: list[str],
        cc: list[str] | None,
        bcc: list[str] | None,
        subject: str,
        body: str,
        attachments: list[str] | None,
        visible: bool,
    ) -> DraftRecord:
        raw = self._run_script(
            "compose_draft.applescript",
            [
                LIST_SEPARATOR.join(to),
                LIST_SEPARATOR.join(cc or []),
                LIST_SEPARATOR.join(bcc or []),
                subject,
                body,
                LIST_SEPARATOR.join(attachments or []),
                "true" if visible else "false",
            ],
        )
        rows = _split_records(raw)
        if not rows or len(rows[0]) < 2:
            raise MailBridgeError("Draft payload was incomplete.")

        draft_id, visible = rows[0][:2]
        return DraftRecord(
            draft_id=_restore_text(draft_id),
            subject=subject,
            to=to,
            cc=cc or [],
            bcc=bcc or [],
            visible=_parse_bool(visible),
        )

    def send_message(
        self,
        to: list[str],
        cc: list[str] | None,
        bcc: list[str] | None,
        subject: str,
        body: str,
        attachments: list[str] | None,
    ) -> SendRecord:
        raw = self._run_script(
            "send_message.applescript",
            [
                LIST_SEPARATOR.join(to),
                LIST_SEPARATOR.join(cc or []),
                LIST_SEPARATOR.join(bcc or []),
                subject,
                body,
                LIST_SEPARATOR.join(attachments or []),
            ],
        )
        rows = _split_records(raw)
        if not rows or len(rows[0]) < 1:
            raise MailBridgeError("Send payload was incomplete.")
        sent_flag = rows[0][0]
        return SendRecord(
            subject=subject,
            to=to,
            cc=cc or [],
            bcc=bcc or [],
            sent=_parse_bool(sent_flag),
        )
