from pathlib import Path
import sqlite3

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
