import random
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


def test_decode_attributed_body_strips_attachment_placeholders_and_accepts_str() -> None:
    assert decode_attributed_body(_attributed_body("\ufffc")) is None
    assert decode_attributed_body(_attributed_body("\ufffc\ufffc look at this")) == "look at this"
    assert decode_attributed_body("prefix NSString\x01+\x05hello") == "hello"
    assert decode_attributed_body(bytearray(_attributed_body("hey"))) == "hey"
    assert decode_attributed_body(memoryview(_attributed_body("hey"))) == "hey"
    assert decode_attributed_body(12345) is None


def test_decode_attributed_body_fuzz_never_raises() -> None:
    rng = random.Random(61)
    samples = [_attributed_body("fuzz me 👋"), _attributed_body("z" * 400)]
    for _ in range(400):
        data = bytearray(rng.choice(samples))
        mutation = rng.randrange(4)
        if mutation == 0:
            data = data[: rng.randrange(len(data) + 1)]
        elif mutation == 1:
            for _ in range(rng.randint(1, 8)):
                data[rng.randrange(len(data))] = rng.randrange(256)
        elif mutation == 2:
            cut = rng.randrange(len(data))
            del data[cut : cut + rng.randint(1, 16)]
        else:
            cut = rng.randrange(len(data))
            data[cut:cut] = bytes(rng.randrange(256) for _ in range(rng.randint(1, 16)))
        result = decode_attributed_body(bytes(data))
        assert result is None or isinstance(result, str)


def test_search_pages_over_decoded_matches_not_archive_bytes(tmp_path) -> None:
    db_path = tmp_path / "chat.db"
    _build_fixture(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("ALTER TABLE message ADD COLUMN attributedBody BLOB")
    # 30 newer blob-only rows whose archive bytes contain "name", "string",
    # "value", ... but whose text does not, plus one older genuine match.
    rows = [
        (100 + index, f"noise-{index}", 1, None, None, "iMessage", 1000 - index, 0, 1, 0, _attributed_body(f"ok {index}"))
        for index in range(30)
    ]
    rows.append((200, "real-match", 1, None, None, "iMessage", 10, 0, 1, 0, _attributed_body("what is your NAME?")))
    rows.append((201, "real-match-2", 1, "my name is Bob", None, "iMessage", 9, 0, 1, 0, None))
    conn.executemany(
        "INSERT INTO message (ROWID, guid, handle_id, text, subject, service, date, is_from_me, is_read,"
        " cache_has_attachments, attributedBody) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.executemany("INSERT INTO chat_message_join VALUES (1, ?)", [(row[0],) for row in rows])
    conn.commit()
    conn.close()
    bridge = MessagesDBBridge(db_path)

    for label in ("name", "string", "value", "number", "attribute"):
        found = [message.message_id for message in bridge.search_messages(query=label, limit=20)]
        assert all(not message_id.startswith("noise-") for message_id in found), label
    assert [message.message_id for message in bridge.search_messages(query="name", limit=20)] == ["real-match", "real-match-2"]
    assert [message.message_id for message in bridge.search_messages(query="name", limit=1)] == ["real-match"]
    assert [message.message_id for message in bridge.search_messages(query="name", limit=1, offset=1)] == ["real-match-2"]
    assert bridge.search_messages(query="name", limit=20, offset=2) == []


def test_search_attributed_body_is_case_insensitive_for_non_ascii(tmp_path) -> None:
    db_path = tmp_path / "chat.db"
    _build_fixture(db_path)
    _add_attributed_body_messages(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO message (ROWID, guid, handle_id, text, subject, service, date, is_from_me, is_read,"
        " cache_has_attachments, attributedBody) VALUES (5, 'msg-5', 1, NULL, NULL, 'iMessage', 5, 0, 1, 0, ?)",
        (_attributed_body("Café ÉTÉ plans"),),
    )
    conn.execute("INSERT INTO chat_message_join VALUES (1, 5)")
    conn.commit()
    conn.close()
    bridge = MessagesDBBridge(db_path)

    assert [message.message_id for message in bridge.search_messages(query="été")] == ["msg-5"]
    assert [message.message_id for message in bridge.search_messages(query="CAFÉ")] == ["msg-5"]


def test_search_attributed_body_matches_case_folded_ascii_queries(tmp_path) -> None:
    # Release review: an ASCII byte prefilter dropped matches that only exist
    # after case folding, so STRASSE never found Straße.
    db_path = tmp_path / "chat.db"
    _build_fixture(db_path)
    _add_attributed_body_messages(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO message (ROWID, guid, handle_id, text, subject, service, date, is_from_me, is_read,"
        " cache_has_attachments, attributedBody) VALUES (6, 'msg-6', 1, NULL, NULL, 'iMessage', 6, 0, 1, 0, ?)",
        (_attributed_body("Meet at the Straße corner"),),
    )
    conn.execute("INSERT INTO chat_message_join VALUES (1, 6)")
    conn.commit()
    conn.close()
    bridge = MessagesDBBridge(db_path)

    assert [message.message_id for message in bridge.search_messages(query="STRASSE")] == ["msg-6"]
    assert [message.message_id for message in bridge.search_messages(query="straße")] == ["msg-6"]


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
