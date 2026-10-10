import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from apple_reminders_mcp import tools
from apple_reminders_mcp.config import load_settings
from apple_reminders_mcp.models import ReminderDetail, ReminderListInfo


class Bridge:
    def __init__(self):
        self.writes = []
        self.reads = []

    def list_lists(self):
        return [ReminderListInfo(list_id=name, title=name, allows_content_modifications=True) for name in ['Work', 'Private']]

    def get_reminder(self, reminder_id):
        return ReminderDetail(reminder_id=reminder_id, title='Task', list_id=reminder_id, list_name=reminder_id)

    def list_reminders(self, *, list_id=None, **kwargs):
        self.reads.append(list_id)
        return [self.get_reminder(name) for name in ['Private', 'Work'] if list_id is None or list_id == name]

    def delete_list(self, list_id):
        self.writes.append(list_id)
        return tools.DeleteReminderListResponse(list_id=list_id, deleted=True)

    def update_reminder(self, reminder_id, **kwargs):
        self.writes.append(kwargs)
        return self.get_reminder(reminder_id)

    def create_reminder(self, **kwargs):
        self.writes.append(kwargs)
        return self.get_reminder(kwargs['list_id'])


@pytest.fixture
def scoped(monkeypatch):
    monkeypatch.setenv('APPLE_REMINDERS_MCP_SAFETY_MODE', 'full_access')
    monkeypatch.setenv('APPLE_REMINDERS_MCP_ALLOWED_LISTS', 'Work')
    load_settings.cache_clear()
    bridge = Bridge()
    monkeypatch.setattr(tools, '_bridge', lambda: bridge)
    yield bridge
    load_settings.cache_clear()


def test_delete_only_resolved_allowed_lists(scoped):
    assert tools.reminders_delete_list('Private').error.error_code == 'LIST_BLOCKED'
    assert tools.reminders_delete_list('event-calendar-id').deleted is False
    assert scoped.writes == []
    assert tools.reminders_delete_list('Work').deleted is True
    assert scoped.writes == ['Work']


@pytest.mark.parametrize('destination,code', [('Private', 'LIST_BLOCKED'), ('unknown', 'LIST_NOT_FOUND')])
def test_update_checks_destination_before_write(scoped, destination, code):
    assert tools.reminders_update_reminder('Work', list_id=destination).error.error_code == code
    assert scoped.writes == []


def test_update_also_checks_source(scoped):
    assert tools.reminders_update_reminder('Private', list_id='Work').error.error_code == 'LIST_BLOCKED'
    assert scoped.writes == []


def test_create_rejects_unresolved_list(scoped):
    assert tools.reminders_create_reminder('Task', 'unknown').error.error_code == 'LIST_NOT_FOUND'
    assert scoped.writes == []


def test_unscoped_read_filters_before_limit(scoped):
    result = tools.reminders_list_reminders(limit=1)
    assert [r.list_name for r in result.reminders] == ['Work']
    assert scoped.reads == ['Work']
    assert [r['list_name'] for r in json.loads(tools.reminders_today_resource())['reminders']] == ['Work']
    assert [r['title'] for r in json.loads(tools.reminders_lists_resource())['lists']] == ['Work']
    assert [r.title for r in tools.reminders_list_lists().lists] == ['Work']


@pytest.mark.skipif(sys.platform != "darwin", reason="EventKit requires macOS")
def test_native_deletion_guard_without_opening_event_store(tmp_path):
    compiler = shutil.which('swiftc')
    if compiler is None:
        pytest.skip('Swift toolchain unavailable')
    source = (Path(__file__).parents[1] / 'src/apple_reminders_mcp/apple_pim_bridge.swift').read_text()
    function = source.split('    static func validateReminderListDeletion(', 1)[1].split('    static func deleteReminderList(', 1)[0]
    program = '''import EventKit
struct BridgeFailure: Error { let errorCode: String; let message: String; let suggestion: String }
struct Probe {
    static func validateReminderListDeletion(''' + function + '''}
func expect(_ mask: EKEntityMask, _ writable: Bool, _ expected: String?) {
    do { try Probe.validateReminderListDeletion(entityTypes: mask, allowsModifications: writable); precondition(expected == nil) }
    catch let failure as BridgeFailure { precondition(failure.errorCode == expected) }
    catch { fatalError("unexpected error") }
}
expect(.event, true, "LIST_NOT_FOUND")
expect([.event, .reminder], true, "LIST_NOT_FOUND")
expect([], true, "LIST_NOT_FOUND")
expect(.reminder, false, "LIST_READ_ONLY")
expect(.reminder, true, nil)
'''
    path = tmp_path / 'guard.swift'
    path.write_text(program)
    binary = tmp_path / 'guard'
    compiled = subprocess.run([compiler, str(path), '-o', str(binary)], capture_output=True, text=True)
    assert compiled.returncode == 0, compiled.stderr
    checked = subprocess.run([str(binary)], capture_output=True, text=True)
    assert checked.returncode == 0, checked.stderr
