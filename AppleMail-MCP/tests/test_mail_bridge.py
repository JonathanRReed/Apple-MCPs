from apple_mail_mcp.mail_bridge import MailBridgeError, decode_message_id, encode_message_id


def test_encode_and_decode_message_id_roundtrip() -> None:
    message_id = encode_message_id("iCloud Personal", "Inbox/Clients", "123:456")

    account, mailbox, apple_id = decode_message_id(message_id)

    assert account == "iCloud Personal"
    assert mailbox == "Inbox/Clients"
    assert apple_id == "123:456"


def test_decode_message_id_rejects_invalid_shape() -> None:
    try:
        decode_message_id("broken-id")
    except MailBridgeError as exc:
        assert "Invalid message_id" in str(exc)
        return

    raise AssertionError("decode_message_id should reject invalid IDs")
