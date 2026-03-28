from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import sqlite3

from apple_messages_mcp.models import AttachmentRecord, ConversationRecord, ConversationSummary, MessageRecord, ParticipantRecord

APPLE_EPOCH = datetime(2001, 1, 1, tzinfo=UTC)


class MessagesDBBridgeError(Exception):
    def __init__(self, error_code: str, message: str, suggestion: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.suggestion = suggestion


class MessagesDBBridge:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def history_accessible(self) -> bool:
        accessible, _ = self.history_access_diagnostic()
        return accessible

    def history_access_diagnostic(self) -> tuple[bool, MessagesDBBridgeError | None]:
        try:
            with self._connect() as conn:
                conn.execute("SELECT 1").fetchone()
            return True, None
        except MessagesDBBridgeError as exc:
            return False, exc

    def list_conversations(self, limit: int = 25, offset: int = 0, unread_only: bool = False) -> list[ConversationSummary]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT c.ROWID AS rowid, c.guid, c.chat_identifier, c.display_name, c.service_name,
                       MAX(m.date) AS last_date
                FROM chat c
                LEFT JOIN chat_message_join cmj ON cmj.chat_id = c.ROWID
                LEFT JOIN message m ON m.ROWID = cmj.message_id
                GROUP BY c.ROWID
                ORDER BY last_date IS NULL, last_date DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()

            conversations = [self._conversation_summary(conn, row) for row in rows]
            if unread_only:
                conversations = [item for item in conversations if item.unread_count > 0]
            return conversations

    def get_conversation(self, chat_id: str, limit: int = 50, offset: int = 0) -> ConversationRecord:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT c.ROWID AS rowid, c.guid, c.chat_identifier, c.display_name, c.service_name,
                       MAX(m.date) AS last_date
                FROM chat c
                LEFT JOIN chat_message_join cmj ON cmj.chat_id = c.ROWID
                LEFT JOIN message m ON m.ROWID = cmj.message_id
                WHERE c.guid = ? OR CAST(c.ROWID AS TEXT) = ?
                GROUP BY c.ROWID
                """,
                (chat_id, chat_id),
            ).fetchone()
            if row is None:
                raise MessagesDBBridgeError("CHAT_NOT_FOUND", f"No chat matched '{chat_id}'.", "List conversations first to discover valid chat ids.")
            summary = self._conversation_summary(conn, row)
            messages = conn.execute(
                """
                SELECT m.ROWID AS message_rowid, m.guid AS message_guid, cmj.chat_id, m.text, m.subject, m.service AS service_name, m.date,
                       COALESCE(m.is_from_me, 0) AS is_from_me, COALESCE(m.cache_has_attachments, 0) AS has_attachments,
                       h.id AS sender_address, h.service AS sender_service, h.uncanonicalized_id AS sender_uncanonicalized_address
                FROM chat_message_join cmj
                JOIN message m ON m.ROWID = cmj.message_id
                LEFT JOIN handle h ON h.ROWID = m.handle_id
                WHERE cmj.chat_id = ?
                ORDER BY m.date DESC
                LIMIT ? OFFSET ?
                """,
                (int(row["rowid"]), limit, offset),
            ).fetchall()
            message_records = [self._message_record(item) for item in reversed(messages)]
            return ConversationRecord(**summary.model_dump(), messages=message_records)

    def get_message(self, message_id: str) -> MessageRecord:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT m.ROWID AS message_rowid, m.guid AS message_guid, cmj.chat_id, m.text, m.subject, m.service AS service_name, m.date,
                       COALESCE(m.is_from_me, 0) AS is_from_me, COALESCE(m.cache_has_attachments, 0) AS has_attachments,
                       h.id AS sender_address, h.service AS sender_service, h.uncanonicalized_id AS sender_uncanonicalized_address
                FROM message m
                LEFT JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
                LEFT JOIN handle h ON h.ROWID = m.handle_id
                WHERE m.guid = ? OR CAST(m.ROWID AS TEXT) = ?
                LIMIT 1
                """,
                (message_id, message_id),
            ).fetchone()
            if row is None:
                raise MessagesDBBridgeError("MESSAGE_NOT_FOUND", f"No message matched '{message_id}'.", "Search messages first to discover valid message ids.")
            return self._message_record(row)

    def search_messages(
        self,
        *,
        query: str,
        chat_id: str | None = None,
        sender: str | None = None,
        start_iso: str | None = None,
        end_iso: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MessageRecord]:
        with self._connect() as conn:
            clauses = ["(COALESCE(m.text, '') LIKE ? OR COALESCE(m.subject, '') LIKE ?)"]
            params: list[object] = [f"%{query}%", f"%{query}%"]
            if chat_id is not None:
                clauses.append("(c.guid = ? OR CAST(c.ROWID AS TEXT) = ?)")
                params.extend([chat_id, chat_id])
            if sender is not None:
                clauses.append("h.id = ?")
                params.append(sender)
            if start_iso is not None:
                clauses.append("m.date >= ?")
                params.append(self._iso_to_messages_date(start_iso))
            if end_iso is not None:
                clauses.append("m.date <= ?")
                params.append(self._iso_to_messages_date(end_iso))
            params.extend([limit, offset])
            rows = conn.execute(
                f"""
                SELECT m.ROWID AS message_rowid, m.guid AS message_guid, cmj.chat_id, m.text, m.subject, m.service AS service_name, m.date,
                       COALESCE(m.is_from_me, 0) AS is_from_me, COALESCE(m.cache_has_attachments, 0) AS has_attachments,
                       h.id AS sender_address, h.service AS sender_service, h.uncanonicalized_id AS sender_uncanonicalized_address
                FROM message m
                LEFT JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
                LEFT JOIN chat c ON c.ROWID = cmj.chat_id
                LEFT JOIN handle h ON h.ROWID = m.handle_id
                WHERE {' AND '.join(clauses)}
                ORDER BY m.date DESC
                LIMIT ? OFFSET ?
                """,
                params,
            ).fetchall()
            return [self._message_record(row) for row in rows]

    def list_attachments(self, chat_id: str | None = None, message_id: str | None = None, limit: int = 50, offset: int = 0) -> list[AttachmentRecord]:
        with self._connect() as conn:
            clauses = []
            params: list[object] = []
            if chat_id is not None:
                clauses.append("(c.guid = ? OR CAST(c.ROWID AS TEXT) = ?)")
                params.extend([chat_id, chat_id])
            if message_id is not None:
                clauses.append("(m.guid = ? OR CAST(m.ROWID AS TEXT) = ?)")
                params.extend([message_id, message_id])
            where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            params.extend([limit, offset])
            rows = conn.execute(
                f"""
                SELECT a.ROWID AS attachment_rowid, a.guid AS attachment_guid, a.filename, a.mime_type, a.transfer_name,
                       m.guid AS message_guid, m.ROWID AS message_rowid
                FROM attachment a
                JOIN message_attachment_join maj ON maj.attachment_id = a.ROWID
                JOIN message m ON m.ROWID = maj.message_id
                LEFT JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
                LEFT JOIN chat c ON c.ROWID = cmj.chat_id
                {where_sql}
                ORDER BY a.ROWID DESC
                LIMIT ? OFFSET ?
                """,
                params,
            ).fetchall()
            return [
                AttachmentRecord(
                    attachment_id=str(row["attachment_guid"] or row["attachment_rowid"]),
                    message_id=str(row["message_guid"] or row["message_rowid"]),
                    path=row["filename"],
                    transfer_name=row["transfer_name"],
                    mime_type=row["mime_type"],
                )
                for row in rows
            ]

    def participant_addresses_for_chat(self, chat_id: str) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT h.id
                FROM handle h
                JOIN chat_handle_join chj ON chj.handle_id = h.ROWID
                JOIN chat c ON c.ROWID = chj.chat_id
                WHERE c.guid = ? OR CAST(c.ROWID AS TEXT) = ?
                ORDER BY h.id
                """,
                (chat_id, chat_id),
            ).fetchall()
            return [str(row["id"]) for row in rows if row["id"]]

    def _connect(self) -> sqlite3.Connection:
        if not self.db_path.exists():
            raise MessagesDBBridgeError("DB_NOT_FOUND", f"Messages database '{self.db_path}' was not found.", "Confirm Messages has been used on this Mac and retry.")
        try:
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        except sqlite3.OperationalError as exc:
            message = str(exc)
            lowered = message.lower()
            if "authorization denied" in lowered or ("unable to open database file" in lowered and self.db_path.exists()):
                raise MessagesDBBridgeError(
                    "PERMISSION_DENIED",
                    "Full Disk Access is required to read Apple Messages history.",
                    "Grant Full Disk Access to the host app or terminal and retry.",
                ) from exc
            raise MessagesDBBridgeError("DB_OPEN_FAILED", message, "Inspect the Messages database path and retry.") from exc
        conn.row_factory = sqlite3.Row
        return conn

    def _conversation_summary(self, conn: sqlite3.Connection, row: sqlite3.Row) -> ConversationSummary:
        chat_rowid = int(row["rowid"])
        participants = conn.execute(
            """
            SELECT h.id, h.service, h.uncanonicalized_id
            FROM handle h
            JOIN chat_handle_join chj ON chj.handle_id = h.ROWID
            WHERE chj.chat_id = ?
            ORDER BY h.id
            """,
            (chat_rowid,),
        ).fetchall()
        participant_records = [
            ParticipantRecord(
                handle_id=str(item["id"]),
                address=str(item["id"]),
                service=item["service"],
                uncanonicalized_address=item["uncanonicalized_id"],
            )
            for item in participants
            if item["id"]
        ]
        unread_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM chat_message_join cmj
            JOIN message m ON m.ROWID = cmj.message_id
            WHERE cmj.chat_id = ? AND COALESCE(m.is_from_me, 0) = 0 AND COALESCE(m.is_read, 1) = 0
            """,
            (chat_rowid,),
        ).fetchone()[0]
        last_message_row = conn.execute(
            """
            SELECT m.text, m.subject, m.date
            FROM chat_message_join cmj
            JOIN message m ON m.ROWID = cmj.message_id
            WHERE cmj.chat_id = ?
            ORDER BY m.date DESC
            LIMIT 1
            """,
            (chat_rowid,),
        ).fetchone()
        preview = None
        last_activity = None
        if last_message_row is not None:
            preview = last_message_row["text"] or last_message_row["subject"]
            last_activity = self._messages_date_to_iso(last_message_row["date"])
        return ConversationSummary(
            chat_id=str(row["guid"] or chat_rowid),
            guid=row["guid"],
            display_name=row["display_name"] or row["chat_identifier"],
            service_name=row["service_name"],
            participants=participant_records,
            unread_count=int(unread_count),
            last_activity_at=last_activity,
            last_message_preview=preview,
        )

    def _message_record(self, row: sqlite3.Row) -> MessageRecord:
        sender = None
        if row["sender_address"]:
            sender = ParticipantRecord(
                handle_id=str(row["sender_address"]),
                address=str(row["sender_address"]),
                service=row["sender_service"],
                uncanonicalized_address=row["sender_uncanonicalized_address"],
            )
        return MessageRecord(
            message_id=str(row["message_guid"] or row["message_rowid"]),
            guid=row["message_guid"],
            chat_id=str(row["chat_id"]) if row["chat_id"] is not None else None,
            sender=sender,
            text=row["text"],
            subject=row["subject"],
            service_name=row["service_name"],
            sent_at=self._messages_date_to_iso(row["date"]),
            is_from_me=bool(row["is_from_me"]),
            has_attachments=bool(row["has_attachments"]),
        )

    def _messages_date_to_iso(self, raw_value: object) -> str | None:
        if raw_value is None:
            return None
        numeric = int(raw_value)
        if numeric == 0:
            return None
        if abs(numeric) > 10_000_000_000:
            seconds = numeric / 1_000_000_000
        else:
            seconds = float(numeric)
        return (APPLE_EPOCH + timedelta(seconds=seconds)).astimezone().isoformat(timespec="seconds")

    def _iso_to_messages_date(self, value: str) -> int:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
        delta = parsed - APPLE_EPOCH
        return int(delta.total_seconds() * 1_000_000_000)
