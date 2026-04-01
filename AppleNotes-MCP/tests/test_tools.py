from apple_notes_mcp.config import load_settings
from apple_notes_mcp.models import AccountInfo, FolderInfo, NoteCapabilities, NoteDetail
from apple_notes_mcp import tools


class FakeBridge:
    def list_accounts(self):
        return [
            AccountInfo(account_id="acc-1", name="iCloud", upgraded=True, default_folder_id="folder-1"),
        ]

    def list_folders(self, account_name: str | None = None):
        return [
            FolderInfo(
                folder_id="folder-1",
                name="Personal",
                account_id="acc-1",
                account_name=account_name or "iCloud",
                parent_folder_id=None,
                parent_folder_name=None,
                shared=False,
            )
        ]

    def list_notes(self, account_name: str | None = None, folder_id: str | None = None):
        return [
            NoteDetail(
                note_id="note-1",
                title="Dallas trip",
                account_id="acc-1",
                account_name="iCloud",
                folder_id=folder_id or "folder-1",
                folder_name="Personal",
                created_epoch=10,
                modified_epoch=20,
                password_protected=False,
                shared=False,
                tags=["travel"],
                plaintext="Places to visit",
                preview="Places to visit",
                attachment_count=0,
                capabilities=NoteCapabilities(),
                body_html="<div>Places to visit</div>",
                attachments=[],
            )
        ]

    def get_note(self, note_id: str) -> NoteDetail:
        return self.list_notes()[0]

    def create_note(self, *, title: str, folder_id: str, body_html: str | None = None, tags: list[str] | None = None) -> NoteDetail:
        note = self.list_notes(folder_id=folder_id)[0]
        note.title = title
        return note

    def update_note(self, note_id: str, *, title: str | None = None, body_html: str | None = None, folder_id: str | None = None, tags: list[str] | None = None) -> NoteDetail:
        note = self.list_notes(folder_id=folder_id)[0]
        if title is not None:
            note.title = title
        return note

    def delete_note(self, note_id: str) -> bool:
        return True

    def append_to_note(self, note_id: str, body_html: str) -> NoteDetail:
        note = self.get_note(note_id)
        note.body_html = f"{note.body_html}{body_html}"
        note.plaintext = "Places to visitAdd flights"
        return note

    def move_note(self, note_id: str, folder_id: str) -> NoteDetail:
        return self.list_notes(folder_id=folder_id)[0]

    def create_folder(self, *, folder_name: str, account_name: str, parent_folder_id: str | None = None):
        return FolderInfo(
            folder_id="folder-new",
            name=folder_name,
            account_id="acc-1",
            account_name=account_name,
            parent_folder_id=parent_folder_id,
            parent_folder_name=None,
            shared=False,
        )

    def rename_folder(self, folder_id: str, folder_name: str):
        return FolderInfo(
            folder_id=folder_id,
            name=folder_name,
            account_id="acc-1",
            account_name="iCloud",
            parent_folder_id=None,
            parent_folder_name=None,
            shared=False,
        )

    def delete_folder(self, folder_id: str) -> bool:
        return True


def test_notes_health_reports_capabilities(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_NOTES_MCP_SAFETY_MODE", "full_access")
    load_settings.cache_clear()

    result = tools.notes_health()

    assert result.ok is True
    assert result.capabilities.supports_attachments is True


def test_create_note_returns_structured_note(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_NOTES_MCP_SAFETY_MODE", "full_access")
    load_settings.cache_clear()
    monkeypatch.setattr(tools, "_bridge", lambda: FakeBridge())

    result = tools.notes_create_note(title="Dallas trip", folder_id="folder-1", body_html="<div>Places to visit</div>", tags=["travel"])

    assert result.ok is True
    assert result.note.title == "Dallas trip"


def test_search_notes_rejects_invalid_limit(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_NOTES_MCP_SAFETY_MODE", "full_access")
    load_settings.cache_clear()
    monkeypatch.setattr(tools, "_bridge", lambda: FakeBridge())

    result = tools.notes_search_notes(query="travel", limit=0)

    assert result.ok is False
    assert result.error.error_code == "INVALID_INPUT"


def test_list_folders_accepts_string_limit_and_offset(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_NOTES_MCP_SAFETY_MODE", "full_access")
    load_settings.cache_clear()
    monkeypatch.setattr(tools, "_bridge", lambda: FakeBridge())

    result = tools.notes_list_folders(limit="1", offset="0")

    assert result.ok is True
    assert result.count == 1


def test_append_to_note_preserves_existing_content(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_NOTES_MCP_SAFETY_MODE", "full_access")
    load_settings.cache_clear()
    monkeypatch.setattr(tools, "_bridge", lambda: FakeBridge())

    result = tools.notes_append_to_note(note_id="note-1", body_html="<div>Add flights</div>")

    assert result.ok is True
    assert "Places to visit" in result.note.body_html
    assert "Add flights" in result.note.body_html


def teardown_function() -> None:
    load_settings.cache_clear()
