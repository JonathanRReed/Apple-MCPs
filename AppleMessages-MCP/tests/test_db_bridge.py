import sqlite3
from pathlib import Path

from apple_messages_mcp.messages_db_bridge import MessagesDBBridge


def _build_fixture(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE chat (ROWID INTEGER PRIMARY KEY, guid TEXT, chat_identifier TEXT, display_name TEXT, service_name TEXT);
        CREATE TABLE handle (ROWID INTEGER PRIMARY KEY, id TEXT, service TEXT, uncanonicalized_id TEXT);
        CREATE TABLE chat_handle_join (chat_id INTEGER, handle_id INTEGER);
        CREATE TABLE message (
            ROWID INTEGER PRIMARY KEY,
            guid TEXT,
            handle_id INTEGER,
            text TEXT,
            subject TEXT,
            service TEXT,
            date INTEGER,
            is_from_me INTEGER,
            is_read INTEGER,
            cache_has_attachments INTEGER
        );
        CREATE TABLE chat_message_join (chat_id INTEGER, message_id INTEGER);
        CREATE TABLE attachment (ROWID INTEGER PRIMARY KEY, guid TEXT, filename TEXT, mime_type TEXT, transfer_name TEXT);
        CREATE TABLE message_attachment_join (message_id INTEGER, attachment_id INTEGER);
        INSERT INTO chat VALUES (1, 'chat-guid-1', 'chat-1', 'Alice', 'iMessage');
        INSERT INTO handle VALUES (1, '+15551234567', 'iMessage', '+15551234567');
        INSERT INTO chat_handle_join VALUES (1, 1);
        INSERT INTO message VALUES (1, 'msg-1', 1, 'hello there', NULL, 'iMessage', 1, 0, 0, 0);
        INSERT INTO message VALUES (2, 'msg-2', NULL, 'hi back', NULL, 'iMessage', 2, 1, 1, 1);
        INSERT INTO chat_message_join VALUES (1, 1);
        INSERT INTO chat_message_join VALUES (1, 2);
        INSERT INTO attachment VALUES (1, 'att-1', '/tmp/file.png', 'image/png', 'file.png');
        INSERT INTO message_attachment_join VALUES (2, 1);
        """
    )
    conn.commit()
    conn.close()


def test_list_conversations_returns_summary(tmp_path) -> None:
    db_path = tmp_path / "chat.db"
    _build_fixture(db_path)
    bridge = MessagesDBBridge(db_path)

    conversations = bridge.list_conversations()

    assert len(conversations) == 1
    assert conversations[0].chat_id == "chat-guid-1"
    assert conversations[0].participants[0].address == "+15551234567"


def test_get_message_and_attachments(tmp_path) -> None:
    db_path = tmp_path / "chat.db"
    _build_fixture(db_path)
    bridge = MessagesDBBridge(db_path)

    message = bridge.get_message("msg-2")
    attachments = bridge.list_attachments(message_id="msg-2")

    assert message.is_from_me is True
    assert attachments[0].transfer_name == "file.png"


def test_history_access_diagnostic_reports_missing_db(tmp_path) -> None:
    bridge = MessagesDBBridge(tmp_path / "missing-chat.db")

    accessible, error = bridge.history_access_diagnostic()

    assert accessible is False
    assert error is not None
    assert error.error_code == "DB_NOT_FOUND"


def test_latest_service_for_chat_returns_most_recent_service(tmp_path) -> None:
    db_path = tmp_path / "chat.db"
    _build_fixture(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO message VALUES (9, 'msg-9', 1, 'later sms', NULL, 'SMS', 9, 0, 1, 0)")
    conn.execute("INSERT INTO chat_message_join VALUES (1, 9)")
    conn.commit()
    conn.close()
    bridge = MessagesDBBridge(db_path)

    assert bridge.latest_service_for_chat("chat-guid-1") == "SMS"
    assert bridge.latest_service_for_chat("missing") is None


def test_latest_service_for_chat_skips_failed_sends(tmp_path) -> None:
    db_path = tmp_path / "chat.db"
    _build_fixture(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("ALTER TABLE message ADD COLUMN error INTEGER DEFAULT 0")
    conn.execute("INSERT INTO message (ROWID, guid, handle_id, text, service, date, is_from_me, is_read, cache_has_attachments, error)"
                 " VALUES (8, 'msg-8', 1, 'old sms', 'SMS', 8, 1, 1, 0, 0)")
    # A newer iMessage that was never delivered must not decide the thread's service.
    conn.execute("INSERT INTO message (ROWID, guid, handle_id, text, service, date, is_from_me, is_read, cache_has_attachments, error)"
                 " VALUES (9, 'msg-9', 1, 'Hi', 'iMessage', 9, 1, 1, 0, 22)")
    conn.executemany("INSERT INTO chat_message_join VALUES (1, ?)", [(8,), (9,)])
    conn.commit()
    conn.close()

    assert MessagesDBBridge(db_path).latest_service_for_chat("chat-guid-1") == "SMS"
