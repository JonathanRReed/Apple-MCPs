import asyncio
import json

import pytest

from apple_agent_mcp import tools
from apple_agent_mcp.config import load_settings
from apple_agent_mcp.models import AssistantPreferences


def forbidden(*args, **kwargs):
    pytest.fail('automatic discovery must not read app data or request permissions')


def test_overview_tool_and_resource_defer_permission_sensitive_data(monkeypatch):
    monkeypatch.setattr(tools, '_domain_health', lambda: {})
    monkeypatch.setattr(tools, '_get_preferences', AssistantPreferences)
    for name in ('files_recent_resource', 'files_recent_locations_resource', 'files_icloud_status_resource', 'system_status_resource', 'system_context_resource', 'system_settings_resource', 'calendar_calendars_resource', 'reminders_lists_resource', 'messages_recent_resource', 'contacts_directory_resource', 'notes_recent_resource', 'shortcuts_all_resource', '_mailboxes_resource'):
        monkeypatch.setattr(tools, name, forbidden, raising=False)
    monkeypatch.setattr(tools, 'maps_status_resource', lambda: '{}')
    for payload in (json.loads(tools.apple_overview_resource()), tools.apple_overview().overview):
        for domain in ('files', 'files_recent_locations', 'files_icloud_status', 'system', 'system_context', 'system_settings', 'calendar', 'reminders', 'messages', 'contacts', 'notes', 'shortcuts', 'mail'):
            assert payload['resources'][domain]['status'] == 'not_probed'
            assert payload['resources'][domain]['ok'] is False


@pytest.mark.parametrize("existing", [True, False])
def test_default_detection_is_passive_and_does_not_write_preferences(monkeypatch, tmp_path, existing):
    path = tmp_path / 'prefs.json'
    if existing:
        path.write_text('{"default_mail_account":"existing"}\n')
    original = path.read_bytes() if existing else None
    monkeypatch.setenv('APPLE_AGENT_MCP_STATE_FILE', str(path))
    load_settings.cache_clear()
    monkeypatch.setattr(tools, '_detect_preferences', forbidden)
    monkeypatch.setattr(tools, '_save_preferences', forbidden)
    result = tools.apple_detect_defaults()
    assert result.ok is True
    assert result.preferences.default_mail_account == ('existing' if existing else None)
    assert result.probe_status == 'not_probed'
    assert result.detected == [] and result.count == 0
    assert (path.read_bytes() if path.exists() else None) == original
    load_settings.cache_clear()


def test_detection_annotation_reports_preference_write():
    tool = next(item for item in asyncio.run(tools.mcp.list_tools()) if item.name == 'apple_detect_defaults')
    assert tool.annotations.read_only_hint is False
    assert tool.input_schema['properties']['probe_apps']['default'] is False


@pytest.mark.parametrize('domain', ['reminders', 'notes'])
def test_automatic_target_resolution_only_probes_requested_domain(monkeypatch, domain):
    for name in ('_pick_archive_mailbox', '_pick_default_calendar'):
        monkeypatch.setattr(tools, name, forbidden)
    if domain == 'reminders':
        monkeypatch.setattr(tools, '_pick_default_notes_folder', forbidden)
        monkeypatch.setattr(tools, '_pick_digest_folder', forbidden)
        monkeypatch.setattr(tools, '_pick_default_reminder_list', lambda: ('list', 'General'))
        target, error = tools._resolve_reminder_target(AssistantPreferences(), persist=False)
    else:
        monkeypatch.setattr(tools, '_pick_default_reminder_list', forbidden)
        monkeypatch.setattr(tools, '_pick_default_notes_folder', lambda: ('folder', 'Notes', 'Account'))
        monkeypatch.setattr(tools, '_pick_digest_folder', lambda: (None, None, None))
        target, error = tools._resolve_notes_target(AssistantPreferences(), persist=False)
    assert error is None
    assert target[0] == ('list' if domain == 'reminders' else 'folder')


@pytest.mark.parametrize('entrypoint', ['tool', 'resource'])
def test_overview_does_not_enumerate_shortcuts(monkeypatch, entrypoint):
    from apple_shortcuts_mcp.shortcuts_bridge import ShortcutsBridge

    monkeypatch.setattr(tools, '_domain_health', lambda: {})
    monkeypatch.setattr(tools, '_get_preferences', AssistantPreferences)
    monkeypatch.setattr(tools, 'maps_status_resource', lambda: '{}')
    monkeypatch.setattr(ShortcutsBridge, '_run_cli', forbidden)

    payload = tools.apple_overview().overview if entrypoint == 'tool' else json.loads(tools.apple_overview_resource())

    assert payload['resources']['shortcuts']['status'] == 'not_probed'
    assert payload['resources']['shortcuts']['ok'] is False


def test_explicit_shortcuts_resource_still_returns_library(monkeypatch):
    from apple_shortcuts_mcp.shortcuts_bridge import ShortcutsBridge

    snapshot = {'folders': [], 'shortcuts': [{'name': 'Fixture shortcut', 'identifier': 'fixture-id'}], 'count': 1}
    monkeypatch.setattr(ShortcutsBridge, 'shortcuts_snapshot', lambda self: snapshot)

    contents = list(asyncio.run(tools.mcp.read_resource('shortcuts://all')))

    assert json.loads(contents[0].content) == snapshot
    assert contents[0].mime_type == 'application/json'
