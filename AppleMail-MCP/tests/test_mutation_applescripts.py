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
LOOKUP_SCRIPTS = ("delete_message.applescript", "move_message.applescript", "get_message.applescript")


@pytest.mark.parametrize("name", LOOKUP_SCRIPTS)
def test_lookup_resolves_objects_instead_of_retaining_live_loop_references(name):
    source = (SCRIPTS / name).read_text()
    code = "\n".join(line.split("--", 1)[0] for line in source.splitlines())
    assert not re.search(r"repeat\s+with\s+(?:theAccount|theMailbox|theMessage)\s+in", code, re.IGNORECASE)
    assert "(get every account whose name is accountName)" in code
    assert "(get every mailbox of sourceAccount whose name is mailboxName)" in code
    assert "(get first message of sourceMailbox whose id is numericMessageId)" in code
    assert 'error "MESSAGE_NOT_FOUND"' in code
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
