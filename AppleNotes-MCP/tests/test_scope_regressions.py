import json
from pathlib import Path

import pytest

from apple_notes_mcp import tools
from apple_notes_mcp.config import load_settings
from apple_notes_mcp.models import AttachmentInfo, FolderInfo, NoteDetail
from apple_notes_mcp.notes_bridge import AppleNotesBridge, NotesBridgeError


def note(folder, **extra):
    return NoteDetail(note_id=folder, title='Title', account_id='a', account_name='iCloud', folder_id=folder, folder_name=folder, body_html='<div>Title</div>', **extra)


class Bridge:
    def __init__(self):
        self.writes = []

    def list_folders(self, **kwargs):
        return [FolderInfo(folder_id=n, name=n, account_id='a', account_name='iCloud') for n in ['Work', 'Private']]

    def list_notes(self, **kwargs):
        return [note('Private'), note('Work')]

    def search_notes(self, **kwargs):
        return self.list_notes() if kwargs.get('limit') is None else self.list_notes()[:kwargs['limit']]

    def get_note(self, note_id):
        return note(note_id)

    def update_note(self, *args, **kwargs):
        self.writes.append((args, kwargs))
        return note('Work')

    move_note = update_note
    delete_folder = update_note
    rename_folder = update_note


@pytest.fixture
def scoped(monkeypatch):
    monkeypatch.setenv('APPLE_NOTES_MCP_SAFETY_MODE', 'full_access')
    monkeypatch.setenv('APPLE_NOTES_MCP_ALLOWED_FOLDERS', 'Work')
    monkeypatch.setenv('APPLE_NOTES_MCP_ALLOWED_ACCOUNTS', 'iCloud')
    load_settings.cache_clear()
    bridge = Bridge()
    monkeypatch.setattr(tools, '_bridge', lambda: bridge)
    yield bridge
    load_settings.cache_clear()


def test_resource_and_unscoped_tool_reads_obey_scope(scoped):
    assert [n.folder_name for n in tools.notes_list_notes(limit=1).notes] == ['Work']
    assert [n.folder_name for n in tools.notes_search_notes('Title', limit=1).notes] == ['Work']
    assert [n['folder_name'] for n in json.loads(tools.notes_recent_resource())['notes']] == ['Work']
    assert [n['name'] for n in json.loads(tools.notes_folders_resource())['folders']] == ['Work']
    assert [n.name for n in tools.notes_list_folders().folders] == ['Work']
    with pytest.raises(tools.SafetyError, match='allowed folder'):
        tools.notes_note_resource('Private')


@pytest.mark.parametrize('operation', [tools.notes_update_note, tools.notes_move_note])
@pytest.mark.parametrize('source,destination', [('Private', 'Work'), ('Work', 'Private')])
def test_move_checks_source_and_destination(scoped, operation, source, destination):
    result = operation(source, folder_id=destination)
    assert result.error.error_code == 'FOLDER_BLOCKED'
    assert scoped.writes == []


@pytest.mark.parametrize('operation', [tools.notes_delete_folder, tools.notes_rename_folder])
def test_unknown_folder_never_reaches_write(scoped, operation):
    kwargs = {'folder_name': 'Work'} if operation is tools.notes_rename_folder else {}
    assert operation('unknown', **kwargs).error.error_code == 'FOLDER_NOT_FOUND'
    assert scoped.writes == []


def test_delete_folder_checks_descendants(scoped, monkeypatch):
    child = FolderInfo(folder_id='child', name='Private', account_id='a', account_name='iCloud', parent_folder_id='Work')
    original = scoped.list_folders()
    monkeypatch.setattr(scoped, 'list_folders', lambda: [*original, child])
    assert tools.notes_delete_folder('Work').error.error_code == 'FOLDER_BLOCKED'
    assert scoped.writes == []


@pytest.mark.parametrize('change', [{'title': 'New'}, {'body_html': '<div>New</div>'}, {'tags': ['new']}])
def test_attachment_notes_refuse_content_rewrite(monkeypatch, change):
    bridge = AppleNotesBridge(Path('/tmp/unused'))
    monkeypatch.setattr(bridge, 'get_note', lambda _: note('Work', attachments=[AttachmentInfo(name='fixture.pdf')]))
    monkeypatch.setattr(bridge, '_run_script', lambda *args: pytest.fail('write reached Notes'))
    with pytest.raises(NotesBridgeError) as failure:
        bridge.update_note('Work', **change)
    assert failure.value.error_code == 'NOTE_HAS_ATTACHMENTS'


@pytest.mark.parametrize('created', [None, 0, 995, 1000, 1001, 1100, 4600])
def test_timeout_never_adopts_same_title_note(monkeypatch, created):
    bridge = AppleNotesBridge(Path('/tmp/unused'))
    # Includes a concurrent note inside the request window and a pre-existing
    # note whose local-midnight timestamp would look fresh east of UTC.
    monkeypatch.setattr(bridge, 'list_notes', lambda **kwargs: [note('Work', created_epoch=created)])
    monkeypatch.setattr(bridge, 'get_note', lambda _: pytest.fail('unverified note adopted'))
    monkeypatch.setattr(bridge, 'update_note', lambda *args, **kwargs: pytest.fail('unrelated note overwritten'))
    def timeout(script, *args):
        assert script == 'create_note.applescript'
        raise NotesBridgeError('APPLESCRIPT_TIMEOUT', 'timed out')
    monkeypatch.setattr(bridge, '_run_script', timeout)
    with pytest.raises(NotesBridgeError) as failure:
        bridge.create_note(title='Title', folder_id='Work', body_html='<p>request body</p>', tags=['requesttag'])
    assert failure.value.error_code == 'NOTE_CREATE_STATUS_UNKNOWN'
