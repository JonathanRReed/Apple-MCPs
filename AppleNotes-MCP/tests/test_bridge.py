import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from apple_notes_mcp.notes_bridge import AppleNotesBridge, NotesBridgeError


def _note_payload(note_id: str, title: str, created_epoch: int = 0) -> dict[str, object]:
    return {
        "note_id": note_id,
        "title": title,
        "account_id": "acc-1",
        "account_name": "iCloud",
        "folder_id": "folder-1",
        "folder_name": "Personal",
        "created_epoch": created_epoch,
        "modified_epoch": created_epoch,
        "password_protected": False,
        "shared": False,
        "attachment_count": 0,
        "plaintext": "",
        "body_html": "",
        "attachments": [],
    }


def test_list_accounts_normalizes_payload(monkeypatch) -> None:
    bridge = AppleNotesBridge(Path("/tmp/scripts"))

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        assert script_name == "list_accounts.applescript"
        return {
            "items": [
                {
                    "account_id": "acc-1",
                    "name": "iCloud",
                    "upgraded": True,
                    "default_folder_id": "folder-1",
                }
            ]
        }

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)
    accounts = bridge.list_accounts()

    assert len(accounts) == 1
    assert accounts[0].name == "iCloud"


def test_search_notes_derives_tags(monkeypatch) -> None:
    bridge = AppleNotesBridge(Path("/tmp/scripts"))

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        if script_name == "list_notes.applescript":
            return {
                "items": [
                    {
                        "note_id": "note-1",
                        "title": "Dallas trip",
                        "account_id": "acc-1",
                        "account_name": "iCloud",
                        "folder_id": "folder-1",
                        "folder_name": "Personal",
                        "created_epoch": 10,
                        "modified_epoch": 20,
                        "password_protected": False,
                        "shared": False,
                        "attachment_count": 0,
                        "plaintext": "Places to visit #travel #ideas",
                    }
                ]
            }
        if script_name == "list_folders.applescript":
            return {
                "items": [
                    {
                        "folder_id": "folder-1",
                        "name": "Personal",
                        "account_id": "acc-1",
                        "account_name": "iCloud",
                        "parent_folder_id": None,
                        "parent_folder_name": None,
                        "shared": False,
                    }
                ]
            }
        raise AssertionError(f"Unexpected script: {script_name}")

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)
    notes = bridge.search_notes("travel")

    assert len(notes) == 1
    assert notes[0].tags == ["travel", "ideas"]


def test_get_note_raises_when_missing(monkeypatch) -> None:
    bridge = AppleNotesBridge(Path("/tmp/scripts"))

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        assert script_name == "get_note.applescript"
        return {"found": False}

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)

    try:
        bridge.get_note("note-1")
    except NotesBridgeError as exc:
        assert exc.error_code == "NOTE_NOT_FOUND"
    else:
        raise AssertionError("Expected NotesBridgeError")


def test_get_note_uses_cached_body_when_notes_returns_empty(monkeypatch) -> None:
    bridge = AppleNotesBridge(Path("/tmp/scripts"))
    bridge._body_html_cache["note-1"] = "<div>Dallas trip</div><div><br></div><div>Places to visit</div>"
    bridge._folder_by_id = lambda folder_id: None  # type: ignore[method-assign]
    monkeypatch.setattr(bridge, "list_attachments", lambda note_id: [])

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        assert script_name == "get_note.applescript"
        return {
            "found": True,
            "note": {
                "note_id": "note-1",
                "title": "Dallas trip",
                "account_id": "acc-1",
                "account_name": "iCloud",
                "folder_id": "folder-1",
                "folder_name": "Personal",
                "created_epoch": 0,
                "modified_epoch": 0,
                "password_protected": False,
                "shared": False,
                "attachment_count": 0,
                "plaintext": "",
                "body_html": "",
                "attachments": [],
            },
        }

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)

    detail = bridge.get_note("note-1")

    assert detail.body_html == "<div>Dallas trip</div><div><br></div><div>Places to visit</div>"


def test_create_note_uses_update_path_when_body_or_tags_present(monkeypatch) -> None:
    bridge = AppleNotesBridge(Path("/tmp/scripts"))

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        if script_name == "create_note.applescript":
            assert args[2] == ""
            assert args[3] == ""
            return {
                "note": {
                    "note_id": "note-1",
                    "title": "Draft title",
                    "account_id": "acc-1",
                    "account_name": "iCloud",
                    "folder_id": "folder-1",
                    "folder_name": "Personal",
                    "created_epoch": 0,
                    "modified_epoch": 0,
                    "password_protected": False,
                    "shared": False,
                    "attachment_count": 0,
                    "plaintext": "",
                    "body_html": "",
                    "attachments": [],
                }
            }
        if script_name == "list_folders.applescript":
            return {
                "items": [
                    {
                        "folder_id": "folder-1",
                        "name": "Personal",
                        "account_id": "acc-1",
                        "account_name": "iCloud",
                        "parent_folder_id": None,
                        "parent_folder_name": None,
                        "shared": False,
                    }
                ]
            }
        raise AssertionError(f"Unexpected script: {script_name}")

    def fake_update_note(note_id: str, **kwargs):
        assert note_id == "note-1"
        assert kwargs["title"] == "Dallas trip"
        assert kwargs["body_html"] == "<div>Dallas trip</div><div><br></div><div>Places to visit</div>"
        assert kwargs["tags"] == ["travel"]
        return bridge._normalize_detail(
            {
                "note_id": "note-1",
                "title": "Dallas trip",
                "account_id": "acc-1",
                "account_name": "iCloud",
                "folder_id": "folder-1",
                "folder_name": "Personal",
                "created_epoch": 0,
                "modified_epoch": 0,
                "password_protected": False,
                "shared": False,
                "attachment_count": 0,
                "plaintext": "Places to visit #travel",
                "body_html": "<div>Places to visit</div>",
                "attachments": [],
            }
        )

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)
    monkeypatch.setattr(bridge, "update_note", fake_update_note)

    detail = bridge.create_note(
        title="Dallas trip",
        folder_id="folder-1",
        body_html="<div>Places to visit</div>",
        tags=["travel"],
    )

    assert detail.title == "Dallas trip"
    assert detail.body_html == "<div>Places to visit</div>"


def test_run_script_times_out_with_structured_error(monkeypatch, tmp_path) -> None:
    # Regression for issue #6: subprocess.run had no timeout, so a stalled
    # osascript blocked the MCP response forever.
    (tmp_path / "list_accounts.applescript").write_text("on run argv\nend run\n")
    bridge = AppleNotesBridge(tmp_path, script_timeout_seconds=5)

    def fake_run(*args, **kwargs):
        assert kwargs["timeout"] == 5
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=5)

    monkeypatch.setattr("apple_notes_mcp.notes_bridge.subprocess.run", fake_run)

    try:
        bridge._run_script("list_accounts.applescript")
    except NotesBridgeError as exc:
        assert exc.error_code == "APPLESCRIPT_TIMEOUT"
    else:
        raise AssertionError("Expected NotesBridgeError")


def test_create_note_recovers_note_after_create_timeout(monkeypatch) -> None:
    # Issue #6's ambiguous-commit case: Notes committed `make new note` but the
    # script stalled afterwards. The deterministic post-timeout lookup must
    # return the created note instead of surfacing an ambiguous failure.
    bridge = AppleNotesBridge(Path("/tmp/scripts"))
    bridge._folder_by_id = lambda folder_id: None  # type: ignore[method-assign]
    monkeypatch.setattr(bridge, "list_attachments", lambda note_id: [])

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        if script_name == "create_note.applescript":
            raise NotesBridgeError("APPLESCRIPT_TIMEOUT", "timed out")
        if script_name == "list_notes.applescript":
            return {"items": [_note_payload("note-9", "Disposable title", created_epoch=int(time.time()))]}
        if script_name == "get_note.applescript":
            return {"found": True, "note": _note_payload("note-9", "Disposable title", created_epoch=int(time.time()))}
        raise AssertionError(f"Unexpected script: {script_name}")

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)

    detail = bridge.create_note(title="Disposable title", folder_id="folder-1")

    assert detail.note_id == "note-9"


def test_create_note_raises_status_unknown_when_recovery_finds_nothing(monkeypatch) -> None:
    bridge = AppleNotesBridge(Path("/tmp/scripts"))
    bridge._folder_by_id = lambda folder_id: None  # type: ignore[method-assign]

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        if script_name == "create_note.applescript":
            raise NotesBridgeError("APPLESCRIPT_TIMEOUT", "timed out")
        if script_name == "list_notes.applescript":
            return {"items": []}
        raise AssertionError(f"Unexpected script: {script_name}")

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)

    try:
        bridge.create_note(title="Disposable title", folder_id="folder-1")
    except NotesBridgeError as exc:
        assert exc.error_code == "NOTE_CREATE_STATUS_UNKNOWN"
        assert "Do not retry blindly" in (exc.suggestion or "")
    else:
        raise AssertionError("Expected NotesBridgeError")


def test_create_note_recovery_ignores_stale_same_title_note(monkeypatch) -> None:
    # A lone match created long ago is a pre-existing note, not the one this
    # call tried to create — recovery must not claim it as a fresh create.
    bridge = AppleNotesBridge(Path("/tmp/scripts"))
    bridge._folder_by_id = lambda folder_id: None  # type: ignore[method-assign]

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        if script_name == "create_note.applescript":
            raise NotesBridgeError("APPLESCRIPT_TIMEOUT", "timed out")
        if script_name == "list_notes.applescript":
            return {"items": [_note_payload("note-old", "Disposable title", created_epoch=int(time.time()) - 86_400)]}
        raise AssertionError(f"Unexpected script: {script_name}")

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)

    try:
        bridge.create_note(title="Disposable title", folder_id="folder-1")
    except NotesBridgeError as exc:
        assert exc.error_code == "NOTE_CREATE_STATUS_UNKNOWN"
    else:
        raise AssertionError("Expected NotesBridgeError")


def test_create_note_reports_note_id_when_post_create_update_fails(monkeypatch) -> None:
    bridge = AppleNotesBridge(Path("/tmp/scripts"))
    bridge._folder_by_id = lambda folder_id: None  # type: ignore[method-assign]

    def fake_run_script(script_name: str, *args: str) -> dict[str, object]:
        assert script_name == "create_note.applescript"
        return {"note": _note_payload("note-1", "Dallas trip")}

    def fake_update_note(note_id: str, **kwargs):
        raise NotesBridgeError("APPLESCRIPT_TIMEOUT", "timed out")

    monkeypatch.setattr(bridge, "_run_script", fake_run_script)
    monkeypatch.setattr(bridge, "update_note", fake_update_note)
    monkeypatch.setattr("apple_notes_mcp.notes_bridge.time.sleep", lambda _seconds: None)

    try:
        bridge.create_note(title="Dallas trip", folder_id="folder-1", body_html="<div>Places to visit</div>")
    except NotesBridgeError as exc:
        assert "note-1" in exc.message
        assert "note-1" in (exc.suggestion or "")
    else:
        raise AssertionError("Expected NotesBridgeError")


def test_normalize_detail_uses_override_when_notes_readback_is_empty() -> None:
    bridge = AppleNotesBridge(Path("/tmp/scripts"))
    bridge._folder_by_id = lambda folder_id: None  # type: ignore[method-assign]

    detail = bridge._normalize_detail(
        {
            "note_id": "note-1",
            "title": "Dallas trip",
            "account_id": "acc-1",
            "account_name": "iCloud",
            "folder_id": "folder-1",
            "folder_name": "Personal",
            "created_epoch": 0,
            "modified_epoch": 0,
            "password_protected": False,
            "shared": False,
            "attachment_count": 0,
            "plaintext": "",
            "body_html": "",
            "attachments": [],
        },
        body_html_override="<div>Dallas trip</div><div><br></div><div>Places to visit</div>",
    )

    assert detail.body_html == "<div>Dallas trip</div><div><br></div><div>Places to visit</div>"


def test_prepare_body_html_prefixes_title_when_first_line_differs() -> None:
    bridge = AppleNotesBridge(Path("/tmp/scripts"))

    body_html = bridge._prepare_body_html("Dallas trip", "<div>Places to visit</div>")

    assert body_html == "<div>Dallas trip</div><div><br></div><div>Places to visit</div>"


@pytest.mark.skipif(
    sys.platform != "darwin" or shutil.which("osacompile") is None,
    reason="osacompile is only available on macOS",
)
def test_mutation_scripts_compile(tmp_path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    scripts_dir = repo_root / "src" / "apple_notes_mcp" / "applescripts"
    scripts = (
        scripts_dir / "create_note.applescript",
        scripts_dir / "delete_note.applescript",
        scripts_dir / "update_note.applescript",
        scripts_dir / "move_note.applescript",
        scripts_dir / "delete_folder.applescript",
    )

    for script_path in scripts:
        compiled_path = tmp_path / f"{script_path.stem}.scpt"
        completed = subprocess.run(
            ["osacompile", "-o", str(compiled_path), str(script_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr or completed.stdout


def test_mutation_helpers_use_explicit_notes_account_scope() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    scripts_dir = repo_root / "src" / "apple_notes_mcp" / "applescripts"
    scripts = (
        scripts_dir / "create_note.applescript",
        scripts_dir / "delete_note.applescript",
        scripts_dir / "update_note.applescript",
        scripts_dir / "move_note.applescript",
    )

    for script_path in scripts:
        source = script_path.read_text()
        assert "tell application \"Notes\"" in source


def test_create_note_sets_body_after_creation() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    source = (repo_root / "src" / "apple_notes_mcp" / "applescripts" / "create_note.applescript").read_text()

    assert 'set newNote to make new note at targetFolder with properties {name:titleText}' in source
    assert "set body of newNote to noteBody" in source


def test_update_note_sets_title_after_body_update() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    source = (repo_root / "src" / "apple_notes_mcp" / "applescripts" / "update_note.applescript").read_text()

    assert source.index("set body of noteRef to my compose_note_body(noteBody, tagsCsv)") < source.index('if titleText is not "" then set name of noteRef to titleText')
