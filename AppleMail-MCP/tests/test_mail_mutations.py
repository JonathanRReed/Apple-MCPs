"""Boundary tests using the real bridge; no Mail account is accessed."""

from pathlib import Path
from subprocess import CompletedProcess

import pytest

from apple_mail_mcp import mail_bridge
from apple_mail_mcp.config import Settings
from apple_mail_mcp.mail_bridge import AppleMailBridge, MailBridgeError, encode_message_id
from apple_mail_mcp.models import SafetyProfile
from apple_mail_mcp.permissions import SafetyPolicyError
from apple_mail_mcp.tools import mail_archive_thread_tool, mail_delete_message_tool, mail_move_message_tool

ACCOUNT = 'Google | Büro "Primary"'
MAILBOX = "INBOX"
DESTINATION = "[Gmail]/Alle Nachrichten"
MESSAGE_ID = encode_message_id(ACCOUNT, MAILBOX, "98765")


@pytest.mark.parametrize("operation,target_account", [("delete", None), ("move", None), ("move", 'Work "Archive"')])
def test_mutation_passes_exact_decoded_identity_as_argv(monkeypatch, operation, target_account):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        output = "true\x1e" if operation == "delete" else f"true\x1f{DESTINATION}\x1e"
        return CompletedProcess(command, 0, output, "")

    monkeypatch.setattr(mail_bridge, "run", run)
    bridge = AppleMailBridge()
    if operation == "delete":
        result = bridge.delete_message(MESSAGE_ID)
        assert result.deleted is True
        expected_args = [ACCOUNT, MAILBOX, "98765"]
    else:
        result = bridge.move_message(MESSAGE_ID, DESTINATION, target_account)
        assert result.moved is True
        assert result.target_mailbox == DESTINATION
        expected_args = [ACCOUNT, MAILBOX, "98765", DESTINATION, target_account or ""]
    assert result.message_id == MESSAGE_ID
    assert len(calls) == 1
    command, kwargs = calls[0]
    assert command[0] == "osascript"
    assert Path(command[1]).name == f"{operation}_message.applescript"
    assert command[2:] == expected_args
    assert not kwargs.get("shell", False)


@pytest.mark.parametrize("operation", ["delete", "move"])
def test_native_error_is_not_swallowed_or_retried(monkeypatch, operation):
    calls = []
    error = '„Mail“ hat einen Fehler erhalten: Objekt kann nicht gelesen werden. (-1728)'

    def run(command, **kwargs):
        calls.append(command)
        # An error must win even if partial stdout resembles a successful reply.
        return CompletedProcess(command, 1, "true\x1fArchive\x1e", error)

    monkeypatch.setattr(mail_bridge, "run", run)
    bridge = AppleMailBridge()
    with pytest.raises(MailBridgeError) as caught:
        if operation == "delete":
            bridge.delete_message(MESSAGE_ID)
        else:
            bridge.move_message(MESSAGE_ID, DESTINATION)
    assert str(caught.value) == error
    assert len(calls) == 1


@pytest.mark.parametrize("operation", ["delete", "move", "archive"])
def test_readonly_blocks_mutations_before_any_mail_access(monkeypatch, operation):
    def forbidden(*args, **kwargs):
        raise AssertionError("Readonly requests must not invoke osascript")

    monkeypatch.setattr(mail_bridge, "run", forbidden)
    settings = Settings(safety_profile=SafetyProfile.SAFE_READONLY)
    bridge = AppleMailBridge()
    with pytest.raises(SafetyPolicyError):
        if operation == "delete":
            mail_delete_message_tool(bridge, settings, MESSAGE_ID)
        elif operation == "move":
            mail_move_message_tool(bridge, settings, MESSAGE_ID, DESTINATION)
        else:
            mail_archive_thread_tool(bridge, settings, MESSAGE_ID, DESTINATION)
