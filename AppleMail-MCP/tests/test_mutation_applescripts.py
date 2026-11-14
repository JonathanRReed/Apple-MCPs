"""Issue #23 guards and safe native checks; these never execute Mail mutations.

Source checks prevent reintroducing the live-list lookup pattern. On macOS we
also compile the actual packaged scripts and execute only their pure handlers.
Neither kind of check replaces a live Mail/Gmail round-trip test.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "src" / "apple_mail_mcp" / "applescripts"
LOOKUP_SCRIPTS = (
    "delete_message.applescript",
    "move_message.applescript",
    "get_message.applescript",
    "mark_message.applescript",
    "reply_message.applescript",
    "forward_message.applescript",
)
SENDER_SCRIPTS = (
    "compose_draft.applescript",
    "send_message.applescript",
    "reply_message.applescript",
    "forward_message.applescript",
)


@pytest.mark.parametrize("name", LOOKUP_SCRIPTS)
def test_lookup_resolves_objects_instead_of_retaining_live_loop_references(name):
    source = (SCRIPTS / name).read_text()
    code = "\n".join(line.split("--", 1)[0] for line in source.splitlines())
    assert not re.search(r"repeat\s+with\s+(?:theAccount|theMailbox|theMessage)\s+in", code, re.IGNORECASE)
    assert "(get every account whose name is accountName)" in code
    assert "(get every mailbox of sourceAccount whose name is mailboxName)" in code
    assert "(get first message of sourceMailbox whose id is numericMessageId)" in code
    assert 'if errorNumber is in {-1728, -1719} then error "MESSAGE_NOT_FOUND"' in code
    # Walking `id of` every message took minutes on a few-thousand-message mailbox.
    assert not re.search(r"id of \w+\) as text\) is appleId", code)
    assert 'error "INVALID_MESSAGE_ID"' in code
    assert 'if (id of targetMessage) is not numericMessageId then error "MESSAGE_ID_MISMATCH"' in code
    if name == "move_message.applescript":
        assert "(get every account whose name is targetAccountName)" in code
        assert "(get every mailbox of destAccount whose name is targetMailboxName)" in code


@pytest.fixture(scope="module", params=LOOKUP_SCRIPTS)
def compiled_script(request, tmp_path_factory):
    if sys.platform != "darwin":
        pytest.skip("AppleScript compilation and execution require macOS")
    destination = tmp_path_factory.mktemp("mail-script") / (request.param + ".scpt")
    # Compile only. Do not execute the script's run handler or access user mail.
    result = subprocess.run(
        ["osacompile", "-o", str(destination), str(SCRIPTS / request.param)],
        capture_output=True, text=True, timeout=45, check=False,
    )
    assert result.returncode == 0, result.stderr
    return destination


def run_pure_handler(compiled_script, body, *args):
    harness = (
        "on run argv\n"
        "    set subjectScript to load script (POSIX file (item 1 of argv))\n"
        f"    {body}\n"
        "end run\n"
    )
    return subprocess.run(
        ["osascript", "-", str(compiled_script), *args],
        input=harness, capture_output=True, text=True, timeout=15, check=False,
    )


def test_native_resolver_materializes_the_selected_value(compiled_script):
    result = run_pure_handler(compiled_script, '''set matches to {"Original"}
    set chosen to subjectScript's requireSingleMatch(matches, "MISSING", "AMBIGUOUS")
    set item 1 of matches to "Changed"
    return chosen''')
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "Original"


@pytest.mark.parametrize("items,error", [('{}', "MISSING"), ('{"a", "b"}', "AMBIGUOUS")])
def test_native_resolver_rejects_missing_and_ambiguous_targets(compiled_script, items, error):
    result = run_pure_handler(
        compiled_script,
        f'return subjectScript\'s requireSingleMatch({items}, "MISSING", "AMBIGUOUS")',
    )
    assert result.returncode != 0
    assert error in result.stderr


def test_native_message_id_is_parsed_without_rounding(compiled_script):
    result = run_pure_handler(compiled_script, "return subjectScript's parseMessageID(item 2 of argv)", "12345")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "12345"


@pytest.mark.parametrize("value", ["", "1.5", "-1", "1e2", "NaN", "99999999999999999999999999"])
def test_native_message_id_rejects_invalid_values(compiled_script, value):
    result = run_pure_handler(compiled_script, "return subjectScript's parseMessageID(item 2 of argv)", value)
    assert result.returncode != 0
    assert "INVALID_MESSAGE_ID" in result.stderr


@pytest.mark.parametrize("name", SENDER_SCRIPTS)
def test_sender_scripts_set_mail_sender_before_touching_system_events(name):
    """`from_account` must go through Mail's `sender` property; System Events is a fallback only."""
    source = (SCRIPTS / name).read_text()
    code = "\n".join(line.split("--", 1)[0] for line in source.splitlines())
    assert "on applySender(theMessage, senderRaw, senderEmail, senderString)" in code
    assert "set sender of theMessage to senderString" in code
    # The raw account name is never written to `sender`; Mail ignores it.
    assert not re.search(r"set sender of \w+ to senderRaw", code)
    # The GUI pop-up path is reached only from applySender, after the direct set failed.
    assert code.count("my selectSenderPopup(") == 1
    assert "my applySender(" in code
    assert "my senderStringForAccount(senderEmail, my fullNameForAccount(matchedAccount))" in code
    assert "my emailForAccount(matchedAccount, senderRaw)" in code
    # Without a readable account address, skip the direct set and use the pop-up.
    assert 'if senderEmail is not "" then\n        set currentSender to ""' in code
    assert "if my senderAddress(currentSender) is senderEmail then" in code
    assert "my senderMatches(currentSender" not in code


@pytest.mark.parametrize("name", SENDER_SCRIPTS)
def test_sender_scripts_resolve_the_account_before_opening_a_compose_window(name):
    code = (SCRIPTS / name).read_text()
    run_handler = code[code.index("on run argv"):]
    resolve = run_handler.index("my resolveAccountBySender(senderRaw)")
    compose = min(
        run_handler.index(marker)
        for marker in ("make new outgoing message", "reply targetMessage", "forward targetMessage")
        if marker in run_handler
    )
    assert resolve < compose


@pytest.mark.parametrize("name", SENDER_SCRIPTS)
def test_sender_scripts_compile(name, tmp_path):
    if sys.platform != "darwin":
        pytest.skip("AppleScript compilation requires macOS")
    # Compile only. Nothing here opens Mail or sends Apple events.
    result = subprocess.run(
        ["osacompile", "-o", str(tmp_path / (name + ".scpt")), str(SCRIPTS / name)],
        capture_output=True, text=True, timeout=45, check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.fixture(scope="module", params=SENDER_SCRIPTS)
def compiled_sender_script(request, tmp_path_factory):
    if sys.platform != "darwin":
        pytest.skip("AppleScript compilation and execution require macOS")
    destination = tmp_path_factory.mktemp("mail-sender-script") / (request.param + ".scpt")
    # Compile only; the tests below run pure text handlers, never Mail.
    result = subprocess.run(
        ["osacompile", "-o", str(destination), str(SCRIPTS / request.param)],
        capture_output=True, text=True, timeout=45, check=False,
    )
    assert result.returncode == 0, result.stderr
    return destination


@pytest.mark.parametrize(
    ("email", "name", "expected"),
    [
        ("me@example.com", "Jonathan Reed", "Jonathan Reed <me@example.com>"),
        ("me@example.com", "", "me@example.com"),
        ("me@example.com", "Reed, Jonathan", '"Reed, Jonathan" <me@example.com>'),
        ("me@example.com", 'Jon "JR" Reed', '"Jon \\"JR\\" Reed" <me@example.com>'),
        # No readable address: never hand back the account name for `sender`.
        ("", "Jonathan Reed", ""),
    ],
)
def test_sender_string_quotes_display_names_and_never_uses_the_account_name(compiled_sender_script, email, name, expected):
    result = run_pure_handler(
        compiled_sender_script,
        "return subjectScript's senderStringForAccount(item 2 of argv, item 3 of argv)",
        email,
        name,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.rstrip("\n") == expected


@pytest.mark.parametrize(
    ("sender", "expected"),
    [
        ("Jonathan Reed <me@example.com>", "me@example.com"),
        ('"Reed, Jonathan" <me@example.com>', "me@example.com"),
        ("  me@example.com ", "me@example.com"),
        ("", ""),
    ],
)
def test_sender_address_extracts_the_angle_bracket_address(compiled_sender_script, sender, expected):
    result = run_pure_handler(compiled_sender_script, "return subjectScript's senderAddress(item 2 of argv)", sender)
    assert result.returncode == 0, result.stderr
    assert result.stdout.rstrip("\n") == expected


def test_recipient_addresses_are_read_through_mail():
    # Outside a Mail tell block `address` is not Mail's term, so the read fails
    # inside its try and every message reports no recipients.
    handler = (SCRIPTS / "get_message.applescript").read_text().split("on joinRecipientAddresses", 1)[1].split("end joinRecipientAddresses", 1)[0]
    assert 'tell application "Mail" to set recipientAddress to address of recipientItem' in handler


@pytest.mark.parametrize(("name", "variable"), (("reply_message.applescript", "replyMessage"), ("forward_message.applescript", "forwardMessage")))
def test_reply_and_forward_never_read_the_outgoing_content(name, variable):
    # In Mail, reading `content` of a new reply or forward makes the next write
    # to it do nothing, so the body is lost and a blank message goes out.
    code = "\n".join(line.split("--", 1)[0] for line in (SCRIPTS / name).read_text().splitlines())
    uses = re.findall(rf"^.*\bcontent of {variable}\b.*$", code, re.MULTILINE)
    assert uses
    for line in uses:
        assert re.fullmatch(rf"\s*(set content of {variable} to \w+|tell content of {variable})", line), line


@pytest.mark.parametrize("name", ("reply_message.applescript", "forward_message.applescript"))
def test_reply_and_forward_send_only_when_asked(name):
    # The server passes "false" below full_access; the script must then save a
    # draft and never reach an unguarded `send`.
    code = "\n".join(line.split("--", 1)[0] for line in (SCRIPTS / name).read_text().splitlines())
    assert 'if (count of argv) ≥ 7 then set sendNow to ((item 7 of argv) is not "false")' in code
    assert re.findall(r"^\s*send \w+$", code, re.MULTILINE) == [re.search(r"^\s*send \w+$", code, re.MULTILINE).group(0)]
    assert re.search(r"if sendNow then\n\s*send \w+\n\s*else\n\s*-?-?.*\n?\s*try\n\s*save \w+", (SCRIPTS / name).read_text())
    assert "return my boolText(sendNow)" in code


DRAFT_SCRIPTS = (
    ("compose_draft.applescript", "newMessage", "shouldBeVisible"),
    ("reply_message.applescript", "replyMessage", "showDraft"),
    ("forward_message.applescript", "forwardMessage", "showDraft"),
)


@pytest.mark.parametrize(("name", "variable", "flag"), DRAFT_SCRIPTS)
def test_draft_scripts_save_then_hide_and_never_close(name, variable, flag):
    # Issue #103. On macOS 27 a hidden draft that is never saved reaches Drafts
    # only at Mail's next autosave. Closing the draft or its window while the
    # save is still running deletes it, so a hidden draft is saved, then hidden.
    code = "\n".join(line.split("--", 1)[0] for line in (SCRIPTS / name).read_text().splitlines())
    run_handler = code[code.index("on run argv"):]
    save = run_handler.index(f"save {variable}")
    hide = run_handler.index(f"set visible of {variable} to false")
    assert save < hide
    assert re.search(rf"if not {flag} then\s*try\s*set visible of {variable} to false", run_handler)
    assert not re.search(r"^\s*close\b", code, re.MULTILINE)


def test_compose_draft_with_a_sender_starts_in_a_window_and_is_hidden_after_the_save():
    # The From pop-up fallback clicks in Mail's front window, and on macOS 27
    # Mail ignores `set visible ... to true` on a draft created hidden. So a
    # draft with from_account must start visible, or the fallback would click
    # in some other window. Hidden drafts without a sender never open one.
    code = "\n".join(line.split("--", 1)[0] for line in (SCRIPTS / "compose_draft.applescript").read_text().splitlines())
    run_handler = code[code.index("on run argv"):]
    assert re.search(r'set openInWindow to shouldBeVisible\s*if senderRaw is not "" then\s*set openInWindow to true', run_handler)
    assert "make new outgoing message with properties {visible:openInWindow," in run_handler
    assert not re.search(r"set visible of \w+ to true", code)
    assert run_handler.index("my applySender(") < run_handler.index("save newMessage") < run_handler.index("set visible of newMessage to false")


@pytest.mark.parametrize(("name", "position"), (("reply_message.applescript", 8), ("forward_message.applescript", 9)))
def test_reply_and_forward_keep_the_draft_window_unless_told_to_hide_it(name, position):
    code = (SCRIPTS / name).read_text()
    assert "set showDraft to true" in code
    assert f'if (count of argv) ≥ {position} then set showDraft to ((item {position} of argv) is not "false")' in code
