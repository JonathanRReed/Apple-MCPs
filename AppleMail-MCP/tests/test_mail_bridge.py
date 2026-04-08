from apple_mail_mcp.mail_bridge import AppleMailBridge, MailBridgeError, decode_message_id, encode_message_id


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


def test_send_message_returns_resolved_from_account(monkeypatch) -> None:
    bridge = AppleMailBridge()

    def fake_run_script(script_name: str, args: list[str]) -> str:
        assert script_name == "send_message.applescript"
        assert args[-1] == "sender@example.com"
        return "true\x1fSubject\x1fiCloud Account\x1e"

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)

    result = bridge.send_message(
        to=["recipient@example.com"],
        cc=None,
        bcc=None,
        subject="Subject",
        body="Body",
        attachments=None,
        from_account="sender@example.com",
    )

    assert result.sent is True
    assert result.from_account == "iCloud Account"
