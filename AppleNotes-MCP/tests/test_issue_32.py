"""Coverage authored for issue #32; live Notes behavior needs macOS validation."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from apple_notes_mcp.notes_bridge import AppleNotesBridge, NotesBridgeError

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "src" / "apple_notes_mcp" / "applescripts"


def note_item(note_id: str, **overrides: object) -> dict[str, object]:
    return {
        "note_id": note_id,
        "title": "Title",
        "account_id": "account-1",
        "account_name": "iCloud",
        "folder_id": "folder-1",
        "folder_name": "Personal",
        "plaintext": "Body-only search needle",
        **overrides,
    }


def test_complete_note_metadata_does_not_fetch_folders(monkeypatch) -> None:
    bridge = AppleNotesBridge(SCRIPTS_DIR)

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        assert script_name == "list_notes.applescript"
        return {"items": [note_item(f"note-{index}") for index in range(110)]}

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)

    notes = bridge.list_notes()

    assert len(notes) == 110
    assert all(note.folder_name == "Personal" for note in notes)


def test_missing_note_metadata_fetches_one_fresh_folder_snapshot_per_request(monkeypatch) -> None:
    bridge = AppleNotesBridge(SCRIPTS_DIR)
    folder_calls = 0
    folder_name = "Personal"

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        nonlocal folder_calls
        if script_name == "list_notes.applescript":
            return {"items": [
                note_item("note-1", account_id="", account_name="", folder_name=""),
                note_item("note-2", account_id="", account_name="", folder_name=""),
                note_item("note-3", folder_id="unknown", folder_name=""),
            ]}
        assert script_name == "list_folders.applescript"
        folder_calls += 1
        return {"items": [{
            "folder_id": "folder-1",
            "name": folder_name,
            "account_id": "account-1",
            "account_name": "iCloud",
        }]}

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)

    first = bridge.list_notes()
    assert folder_calls == 1
    assert [note.folder_name for note in first] == ["Personal", "Personal", ""]
    assert first[0].account_id == "account-1"
    assert first[0].account_name == "iCloud"

    folder_name = "Renamed"
    second = bridge.list_notes()
    assert folder_calls == 2
    assert [note.folder_name for note in second] == ["Renamed", "Renamed", ""]


def test_empty_notes_list_does_not_fetch_folders(monkeypatch) -> None:
    bridge = AppleNotesBridge(SCRIPTS_DIR)

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        assert script_name == "list_notes.applescript"
        return {"items": []}

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)
    assert bridge.list_notes() == []


def test_search_notes_matches_body_without_title_match(monkeypatch) -> None:
    bridge = AppleNotesBridge(SCRIPTS_DIR)

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        assert script_name == "list_notes.applescript"
        return {"items": [note_item("note-1")]}

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)

    assert [note.note_id for note in bridge.search_notes("search needle")] == ["note-1"]


@pytest.mark.parametrize("control_code", range(32))
def test_run_script_preserves_literal_string_controls_and_complex_emoji(monkeypatch, control_code) -> None:
    bridge = AppleNotesBridge(SCRIPTS_DIR)
    value = "before" + chr(control_code) + "after 👩🏽‍💻 👨‍👩‍👧‍👦 🇺🇸 e\u0301"
    output = '{"text":"' + value + '"}'
    monkeypatch.setattr(
        "apple_notes_mcp.notes_bridge.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout=output, stderr=""),
    )

    payload = bridge._run_script("get_note.applescript", "note-1")

    assert payload["text"] == value
    assert json.loads(json.dumps(payload))["text"] == value


def test_run_script_preserves_existing_json_escapes(monkeypatch) -> None:
    bridge = AppleNotesBridge(SCRIPTS_DIR)
    value = 'tab\tline\nquote"backslash\\literal\\n 👩🏽‍💻'
    output = json.dumps({"text": value}, ensure_ascii=False)
    monkeypatch.setattr(
        "apple_notes_mcp.notes_bridge.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout=output, stderr=""),
    )

    assert bridge._run_script("get_note.applescript", "note-1")["text"] == value


@pytest.mark.parametrize("output", ['{"text":\x01}', '{"text":"unescaped " quote"}', "{}junk", "[]"])
def test_run_script_still_rejects_invalid_json_or_non_objects(monkeypatch, output) -> None:
    bridge = AppleNotesBridge(SCRIPTS_DIR)
    monkeypatch.setattr(
        "apple_notes_mcp.notes_bridge.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout=output, stderr=""),
    )

    with pytest.raises(NotesBridgeError) as exc_info:
        bridge._run_script("get_note.applescript", "note-1")

    assert exc_info.value.error_code == "INVALID_SCRIPT_OUTPUT"


@pytest.mark.parametrize("script_name", ["get_note", "list_notes", "create_note", "update_note"])
def test_note_json_fetches_values_in_explicit_notes_context(script_name) -> None:
    source = (SCRIPTS_DIR / f"{script_name}.applescript").read_text()
    handler = source.split("on note_json(", 1)[1].split("end note_json", 1)[0]
    for raw_name, property_name in (
        ("rawNoteId", "id"),
        ("rawTitleText", "name"),
        ("rawPlainText", "plaintext"),
    ):
        assert f'tell application "Notes" to set {raw_name} to {property_name} of n' in handler
        assert f"my safe_text({raw_name})" in handler
    if script_name != "list_notes":
        assert 'tell application "Notes" to set rawBodyHtml to body of n' in handler
        assert "my safe_text(rawBodyHtml)" in handler
    if script_name in {"get_note", "list_notes"}:
        assert 'tell application "Notes" to set rawCreatedDate to creation date of n' in handler
        assert 'tell application "Notes" to set rawModifiedDate to modification date of n' in handler


@pytest.mark.skipif(
    sys.platform != "darwin" or shutil.which("osacompile") is None,
    reason="osacompile is only available on macOS",
)
@pytest.mark.parametrize("script_name", ["get_note", "list_notes"])
def test_notes_read_scripts_compile(tmp_path, script_name) -> None:
    script_path = SCRIPTS_DIR / f"{script_name}.applescript"
    completed = subprocess.run(
        ["osacompile", "-o", str(tmp_path / f"{script_name}.scpt"), str(script_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
