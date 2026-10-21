from pathlib import Path
from subprocess import TimeoutExpired

import pytest

from apple_mail_mcp import mail_bridge
from apple_mail_mcp.config import Settings
from apple_mail_mcp.mail_bridge import (
    AppleMailBridge,
    MailBridgeError,
    MailScriptTimeoutError,
    MailSendStatusUnknownError,
    decode_message_id,
    encode_message_id,
)
from apple_mail_mcp.models import SafetyProfile
from apple_mail_mcp.tools import (
    mail_compose_draft,
    mail_forward_message,
    mail_get_message,
    mail_reply_latest_in_thread,
    mail_reply_message,
    mail_send_message,
)


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


def test_search_messages_reports_unknown_account(monkeypatch) -> None:
    bridge = AppleMailBridge()

    def fake_run_script(script_name: str, args: list[str]) -> str:
        assert script_name == "search_messages.applescript"
        assert args[-1] == "Nope"
        raise MailBridgeError("search_messages.applescript: execution error: ACCOUNT_NOT_FOUND (-2700)")

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)

    with pytest.raises(MailBridgeError) as excinfo:
        bridge.search_messages("*", account="Nope")

    assert str(excinfo.value).startswith("ACCOUNT_NOT_FOUND:")
    assert "'Nope'" in str(excinfo.value)
    assert "mail_list_mailboxes" in str(excinfo.value)


def test_search_messages_without_account_searches_all_accounts(monkeypatch) -> None:
    bridge = AppleMailBridge()

    def fake_run_script(script_name: str, args: list[str]) -> str:
        assert args[-1] == ""
        return "Work\x1fInbox\x1f42\x1fHello\x1fa@example.com\x1fdate\x1ffalse\x1fHello\x1e"

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)

    results = bridge.search_messages("*")

    assert [(item.account, item.subject) for item in results] == [("Work", "Hello")]


def test_forward_message_passes_send_flag_and_reports_draft(monkeypatch) -> None:
    bridge = AppleMailBridge()
    calls: list[list[str]] = []

    def fake_run_script(script_name: str, args: list[str]) -> str:
        calls.append(args)
        sent = args[-1]
        return f"{sent}\x1fFwd: Hello\x1f\x1e"

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)
    message_id = encode_message_id("iCloud", "INBOX", "42")

    draft = bridge.forward_message(message_id, to=["x@example.com"], send=False)
    sent = bridge.forward_message(message_id, to=["x@example.com"])

    assert calls[0][-1] == "false" and calls[1][-1] == "true"
    assert draft.sent is False and draft.draft is True
    assert sent.sent is True and sent.draft is False


def test_run_osascript_times_out_with_actionable_error(monkeypatch) -> None:
    bridge = AppleMailBridge(script_timeout=0.5)

    def fake_run(command, **kwargs):
        assert command[0] == "osascript"
        assert kwargs["timeout"] == 0.5
        raise TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(mail_bridge, "run", fake_run)

    with pytest.raises(MailBridgeError) as excinfo:
        bridge._run_osascript(Path("/tmp/compose_draft.applescript"), [])

    message = str(excinfo.value)
    assert "compose_draft.applescript" in message
    assert "timed out after 0.5s" in message
    assert "consent" in message


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, 120), ("", 120), ("abc", 120), ("-3", 120), ("4", 120), ("5", 5), (" 12 ", 12)],
)
def test_script_timeout_env_parsing(monkeypatch, raw, expected) -> None:
    if raw is None:
        monkeypatch.delenv("APPLE_MAIL_MCP_SCRIPT_TIMEOUT_SECONDS", raising=False)
    else:
        monkeypatch.setenv("APPLE_MAIL_MCP_SCRIPT_TIMEOUT_SECONDS", raw)

    assert AppleMailBridge().script_timeout == expected


MESSAGE_ID = encode_message_id("Work", "INBOX", "42")
GET_MESSAGE_ROW = "\x1f".join(
    ["Work", "INBOX", "42", "Hello", "a@example.com", "", "", "date", "true", "Body", ""]
) + "\x1e"


def _bridge_timing_out_on(monkeypatch, *timing_out: str) -> AppleMailBridge:
    """A real bridge whose osascript times out for the named scripts only."""
    bridge = AppleMailBridge(script_timeout=7)

    def fake_run(command, **kwargs):
        script = Path(command[1]).name
        if script in timing_out:
            raise TimeoutExpired(command, kwargs["timeout"])
        stdout = {"get_message.applescript": GET_MESSAGE_ROW}.get(script, "")
        return mail_bridge.CompletedProcess(command, 0, stdout, "")

    monkeypatch.setattr(mail_bridge, "run", fake_run)
    return bridge


FULL_ACCESS = Settings(safety_profile=SafetyProfile.FULL_ACCESS)
SAFE_MANAGE = Settings(safety_profile=SafetyProfile.SAFE_MANAGE)

SEND_PATHS = [
    pytest.param(
        "send_message.applescript",
        lambda bridge: mail_send_message(["x@example.com"], subject="Hi", from_account="UTD", bridge=bridge, settings=FULL_ACCESS),
        "'UTD' account's Sent mailbox",
        id="send",
    ),
    pytest.param(
        "reply_message.applescript",
        lambda bridge: mail_reply_message(MESSAGE_ID, "Thanks", bridge=bridge, settings=FULL_ACCESS),
        "'Work' account's Sent mailbox",
        id="reply",
    ),
    pytest.param(
        "reply_message.applescript",
        lambda bridge: mail_reply_latest_in_thread(MESSAGE_ID, "Thanks", from_account="me@example.com", bridge=bridge, settings=FULL_ACCESS),
        "'me@example.com' account's Sent mailbox",
        id="reply-latest-in-thread",
    ),
    pytest.param(
        "forward_message.applescript",
        lambda bridge: mail_forward_message(MESSAGE_ID, ["x@example.com"], bridge=bridge, settings=FULL_ACCESS),
        "'Work' account's Sent mailbox",
        id="forward-send",
    ),
]


@pytest.mark.parametrize(("script", "call", "where"), SEND_PATHS)
def test_send_timeout_reports_unknown_status_not_failure(monkeypatch, script, call, where) -> None:
    # Killing osascript does not cancel a send Mail already started, so a
    # timeout must tell the agent to check Sent instead of inviting a retry.
    result = call(_bridge_timing_out_on(monkeypatch, script))

    assert result.ok is False
    assert result.error_code == "SEND_STATUS_UNKNOWN"
    assert "timed out after 7s" in result.message
    assert where in result.suggestion
    assert "Sent Messages" in result.suggestion
    assert "Do not retry" in result.suggestion


def test_send_timeout_without_from_account_names_the_sending_account(monkeypatch) -> None:
    bridge = _bridge_timing_out_on(monkeypatch, "send_message.applescript")

    with pytest.raises(MailSendStatusUnknownError) as excinfo:
        bridge.send_message(["x@example.com"], None, None, "Hi", "Body", None)

    assert "the sending account's Sent mailbox" in excinfo.value.suggestion
    assert isinstance(excinfo.value.__cause__, MailScriptTimeoutError)


NON_SEND_PATHS = [
    pytest.param(
        "compose_draft.applescript",
        lambda bridge: mail_compose_draft(["x@example.com"], subject="Hi", bridge=bridge, settings=FULL_ACCESS),
        "DRAFT_CREATE_FAILED",
        id="draft",
    ),
    pytest.param(
        "forward_message.applescript",
        lambda bridge: mail_forward_message(MESSAGE_ID, ["x@example.com"], bridge=bridge, settings=SAFE_MANAGE),
        "FORWARD_FAILED",
        id="forward-draft",
    ),
    pytest.param(
        "get_message.applescript",
        lambda bridge: mail_get_message(MESSAGE_ID, bridge=bridge),
        "MESSAGE_LOOKUP_FAILED",
        id="get-message",
    ),
    pytest.param(
        "get_message.applescript",
        lambda bridge: mail_reply_latest_in_thread(MESSAGE_ID, "Thanks", bridge=bridge, settings=FULL_ACCESS),
        "THREAD_REPLY_FAILED",
        id="reply-latest-thread-lookup",
    ),
]


@pytest.mark.parametrize(("script", "call", "code"), NON_SEND_PATHS)
def test_non_send_timeout_keeps_ordinary_error(monkeypatch, script, call, code) -> None:
    result = call(_bridge_timing_out_on(monkeypatch, script))

    assert result.ok is False
    assert result.error_code == code
    assert "timed out after 7s" in result.message
    assert "SEND_STATUS_UNKNOWN" not in result.message
