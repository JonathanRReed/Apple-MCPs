from pathlib import Path
import subprocess

from apple_notes_mcp.notes_bridge import AppleNotesBridge, NotesBridgeError


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


def test_mutation_scripts_compile(tmp_path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    scripts = (
        repo_root / "applescripts" / "create_note.applescript",
        repo_root / "applescripts" / "delete_note.applescript",
        repo_root / "applescripts" / "update_note.applescript",
        repo_root / "applescripts" / "move_note.applescript",
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
    scripts = (
        repo_root / "applescripts" / "create_note.applescript",
        repo_root / "applescripts" / "delete_note.applescript",
        repo_root / "applescripts" / "update_note.applescript",
        repo_root / "applescripts" / "move_note.applescript",
    )

    for script_path in scripts:
        source = script_path.read_text()
        assert "tell application \"Notes\"" in source


def test_create_note_sets_body_after_creation() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    source = (repo_root / "applescripts" / "create_note.applescript").read_text()

    assert 'set newNote to make new note at targetFolder with properties {name:titleText}' in source
    assert "set body of newNote to noteBody" in source


def test_update_note_sets_title_after_body_update() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    source = (repo_root / "applescripts" / "update_note.applescript").read_text()

    assert source.index("set body of noteRef to my compose_note_body(noteBody, tagsCsv)") < source.index('if titleText is not "" then set name of noteRef to titleText')
