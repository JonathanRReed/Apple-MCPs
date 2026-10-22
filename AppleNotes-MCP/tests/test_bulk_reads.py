"""Notes read scripts read properties in bulk, and the bulk path builds the same JSON."""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parents[1] / "src" / "apple_notes_mcp" / "applescripts"
READ_SCRIPTS = ("list_notes", "list_folders", "get_note", "list_attachments")
on_macos = pytest.mark.skipif(sys.platform != "darwin" or shutil.which("osascript") is None, reason="AppleScript requires macOS")


def _source(script: str) -> str:
    return (SCRIPTS / f"{script}.applescript").read_text()


def _handlers(script: str, *names: str) -> str:
    source = _source(script)
    blocks = []
    for name in names:
        match = re.search(rf"^on {name}\(.*?^end {name}$", source, flags=re.MULTILINE | re.DOTALL)
        assert match, f"{script} has no handler {name}"
        blocks.append(match.group(0))
    return "\n\n".join(blocks)


def _run_probe(tmp_path: Path, run_body: str, handlers: str) -> dict:
    probe = tmp_path / "probe.applescript"
    probe.write_text(f'use framework "Foundation"\nuse scripting additions\n\non run argv\n{run_body}\nend run\n\n{handlers}\n')
    result = subprocess.run([shutil.which("osascript") or "osascript", str(probe)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout, strict=False)


@pytest.mark.skipif(sys.platform != "darwin" or shutil.which("osacompile") is None, reason="osacompile is only available on macOS")
@pytest.mark.parametrize("script", READ_SCRIPTS)
def test_read_scripts_compile(script, tmp_path) -> None:
    completed = subprocess.run(
        ["osacompile", "-o", str(tmp_path / f"{script}.scpt"), str(SCRIPTS / f"{script}.applescript")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_list_notes_reads_each_property_once_per_folder() -> None:
    source = _source("list_notes")
    for prop in ("id", "name", "plaintext", "creation date", "modification date", "shared"):
        assert re.search(rf"to {prop} of every note of fld\b", source), prop
    assert "id of every attachment of every note of fld" in source
    # The per-note path stays only as a fallback after the bulk read fails.
    assert source.index("of every note of fld") < source.index("repeat with n in notes of fld")


def test_list_folders_reads_each_property_once_per_account() -> None:
    source = _source("list_folders")
    for prop in ("id", "name", "shared", "class of container", "id of container", "name of container"):
        assert f"to {prop} of folders of acc" in source, prop


@pytest.mark.parametrize("script", ["get_note", "list_attachments"])
def test_note_lookup_tries_note_id_before_scanning(script) -> None:
    source = _source(script)
    assert "set directNote to note id targetNoteId" in source
    assert source.index("note id targetNoteId") < source.index("id of every note of fld")
    assert "repeat with n in notes of fld" in source


@on_macos
def test_bulk_note_values_build_the_same_json_as_before(tmp_path) -> None:
    run_body = """
	set createdDate to (current application's NSDate's dateWithTimeIntervalSince1970:1710055800) as date
	set modifiedDate to (current application's NSDate's dateWithTimeIntervalSince1970:4102444800) as date
	set titleText to "Say " & quote & "hi" & quote & " \\\\ there"
	set bodyText to "line 1" & linefeed & "line 2" & return & "#tag"
	set noteA to my note_json_from_values("acc-1", "iCloud", "fld-1", "Notes", "note-1", titleText, bodyText, createdDate, modifiedDate, true, {"att-1", "att-2"})
	set noteB to my note_json_from_values("acc-1", "iCloud", "fld-1", "Notes", "note-2", missing value, "", "not a date", "not a date", false, {})
	return "{" & quote & "items" & quote & ":[" & noteA & "," & noteB & "]}"
"""
    handlers = _handlers(
        "list_notes",
        "note_json_from_values",
        "note_record_json",
        "date_to_epoch",
        "safe_text",
        "json_boolean",
        "json_string",
        "replace_text",
    )
    first, second = _run_probe(tmp_path, run_body, handlers)["items"]
    assert list(first) == [
        "note_id",
        "title",
        "account_id",
        "account_name",
        "folder_id",
        "folder_name",
        "created_epoch",
        "modified_epoch",
        "shared",
        "attachment_count",
        "plaintext",
    ]
    assert first == {
        "note_id": "note-1",
        "title": 'Say "hi" \\ there',
        "account_id": "acc-1",
        "account_name": "iCloud",
        "folder_id": "fld-1",
        "folder_name": "Notes",
        "created_epoch": 1710055800,
        "modified_epoch": 4102444800,
        "shared": True,
        "attachment_count": 2,
        "plaintext": "line 1\nline 2\n#tag",
    }
    # Same fallbacks as the per-note reader: text coercion of missing value, 0 for unreadable dates.
    assert second["title"] == "missing value"
    assert (second["created_epoch"], second["modified_epoch"], second["shared"], second["attachment_count"]) == (0, 0, False, 0)


@on_macos
def test_bulk_folder_values_build_the_same_json_as_before(tmp_path) -> None:
    run_body = """
	tell application "Notes" to set accountClass to account
	set item1 to my folder_json_from_values("acc-1", "iCloud", "fld-1", "Work " & quote & "A" & quote, true, accountClass, "acc-1", "iCloud")
	return "{" & quote & "items" & quote & ":[" & item1 & "]}"
"""
    handlers = _handlers(
        "list_folders",
        "folder_json_from_values",
        "folder_record_json",
        "safe_text",
        "nullable_json_string",
        "json_boolean",
        "json_string",
        "replace_text",
    )
    (item,) = _run_probe(tmp_path, run_body, handlers)["items"]
    assert item == {
        "folder_id": "fld-1",
        "name": 'Work "A"',
        "account_id": "acc-1",
        "account_name": "iCloud",
        "parent_folder_id": None,
        "parent_folder_name": None,
        "shared": True,
    }


def test_list_folders_compares_parent_class_inside_notes_context() -> None:
    # `class of container ... is folder` evaluated outside `tell application "Notes"`
    # never matched, so parent_folder_id was always null and the subfolder
    # allowlist check in notes_delete_folder never fired.
    script = (SCRIPTS / "list_folders.applescript").read_text()
    bulk = script[script.index('tell application "Notes"', script.index("on account_folders_json")) :]
    bulk = bulk[: bulk.index("end tell")]
    assert "is folder" in bulk
    assert "parentIsFolderFlags" in bulk
    fallback = script[script.index("on folder_json(") :]
    fallback = fallback[: fallback.index("end folder_json")]
    assert 'tell application "Notes"' in fallback and "is folder" in fallback
