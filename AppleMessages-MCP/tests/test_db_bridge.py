import sqlite3
from pathlib import Path

from apple_messages_mcp.messages_db_bridge import MessagesDBBridge, decode_attributed_body


def _attributed_body(text: str) -> bytes:
    """Build an attributedBody blob shaped like the NSArchiver typedstream Messages writes."""
    encoded = text.encode("utf-8")
    if len(encoded) < 0x80:
        length = bytes([len(encoded)])
    else:
        length = b"\x81" + len(encoded).to_bytes(2, "little")
    return (
        b"\x04\x0bstreamtyped\x81\xe8\x03\x84\x01@\x84\x84\x84\x12NSAttributedString\x00"
        b"\x84\x84\x08NSObject\x00\x85\x92\x84\x84\x84\x08NSString\x01\x94\x84\x01+"
        + length
        + encoded
        + b"\x86\x84\x02iI\x01\x05\x92\x84\x84\x84\x0cNSDictionary\x00\x94\x84\x01i\x01\x92\x84\x96\x96"
        b"\x1d__kIMMessagePartAttributeName\x86\x92\x84\x84\x84\x08NSNumber\x00\x84\x84\x07NSValue\x00\x94\x84\x01*\x84\x99\x99\x00\x86\x86\x86"
    )


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


def _add_attributed_body_messages(path: Path) -> None:
    # Recent macOS often stores the body only in attributedBody (text is NULL).
    conn = sqlite3.connect(path)
    conn.execute("ALTER TABLE message ADD COLUMN attributedBody BLOB")
    rows = [
        (3, "msg-3", 1, None, None, "iMessage", 3, 0, 0, 0, _attributed_body("see you at dinner")),
        (4, "msg-4", 1, None, None, "iMessage", 4, 0, 0, 0, _attributed_body("long " + "x" * 300)),
    ]
    conn.executemany(
        "INSERT INTO message (ROWID, guid, handle_id, text, subject, service, date, is_from_me, is_read,"
        " cache_has_attachments, attributedBody) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.executemany("INSERT INTO chat_message_join VALUES (1, ?)", [(3,), (4,)])
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


def test_decode_attributed_body_short_and_long_strings() -> None:
    assert decode_attributed_body(_attributed_body("hi 👋")) == "hi 👋"
    long_text = "y" * 1000
    assert decode_attributed_body(_attributed_body(long_text)) == long_text
    assert decode_attributed_body(None) is None
    assert decode_attributed_body(b"") is None
    assert decode_attributed_body(b"not a typedstream") is None


def test_messages_with_only_attributed_body_return_text(tmp_path) -> None:
    db_path = tmp_path / "chat.db"
    _build_fixture(db_path)
    _add_attributed_body_messages(db_path)
    bridge = MessagesDBBridge(db_path)

    conversation = bridge.get_conversation("chat-guid-1", limit=10)
    texts = [message.text for message in conversation.messages]

    assert "see you at dinner" in texts
    assert "long " + "x" * 300 in texts
    assert bridge.get_message("msg-3").text == "see you at dinner"
    assert bridge.list_conversations()[0].last_message_preview == "long " + "x" * 300


def test_search_matches_attributed_body_text_but_not_archive_internals(tmp_path) -> None:
    db_path = tmp_path / "chat.db"
    _build_fixture(db_path)
    _add_attributed_body_messages(db_path)
    bridge = MessagesDBBridge(db_path)

    assert [message.message_id for message in bridge.search_messages(query="DINNER")] == ["msg-3"]
    assert [message.message_id for message in bridge.search_messages(query="hello")] == ["msg-1"]
    assert bridge.search_messages(query="NSDictionary") == []
