import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Lock

import pytest

from apple_contacts_mcp.config import load_settings
from apple_contacts_mcp.contacts_bridge import CONTACTS_HELPER_BUNDLE, AppleContactsBridge, ContactsBridgeError, build_bridge
from apple_mcp_common.native import CODESIGN


def _signed(command):
    return subprocess.CompletedProcess(command, 0, '', '')


def test_native_is_default_and_applescript_is_explicit(monkeypatch):
    monkeypatch.delenv('APPLE_CONTACTS_MCP_BACKEND', raising=False)
    load_settings.cache_clear()
    assert build_bridge().helper_source.name == 'contacts_bridge.swift'
    monkeypatch.setenv('APPLE_CONTACTS_MCP_BACKEND', 'applescript')
    load_settings.cache_clear()
    assert build_bridge().helper_source is None
    load_settings.cache_clear()


def test_native_build_is_cached_by_source_and_installed_atomically(tmp_path, monkeypatch):
    source = tmp_path / 'bridge.swift'
    source.write_text('first revision')
    bridge = AppleContactsBridge(tmp_path, helper_source=source, helper_build_dir=tmp_path / 'build')
    builds = []

    def compile(command, **kwargs):
        if command[0] == CODESIGN:
            return _signed(command)
        builds.append(command)
        assert kwargs['timeout'] == 300
        Path(command[-1]).write_bytes(b'executable')
        return subprocess.CompletedProcess(command, 0, '', '')

    monkeypatch.setattr(subprocess, 'run', compile)
    first = bridge._ensure_native_helper()
    assert first.read_bytes() == b'executable'
    assert bridge._ensure_native_helper() == first
    assert len(builds) == 1
    other = AppleContactsBridge(tmp_path, helper_source=source, helper_build_dir=tmp_path / 'build')
    assert other._ensure_native_helper() == first
    assert len(builds) == 1
    source.write_text('second revision')
    revised = AppleContactsBridge(tmp_path, helper_source=source, helper_build_dir=tmp_path / 'build')
    assert revised._ensure_native_helper() != first
    assert len(builds) == 2


@pytest.mark.parametrize('timeout', [False, True])
def test_failed_compile_never_installs_partial_helper(tmp_path, monkeypatch, timeout):
    source = tmp_path / 'bridge.swift'
    source.write_text('broken source')
    build = tmp_path / 'build'
    bridge = AppleContactsBridge(tmp_path, helper_source=source, helper_build_dir=build)

    def compile(command, **kwargs):
        if command[0] == CODESIGN:
            return _signed(command)
        Path(command[-1]).write_bytes(b'partial')
        if timeout:
            raise subprocess.TimeoutExpired(command, 300)
        return subprocess.CompletedProcess(command, 1, '', 'compile failed')

    monkeypatch.setattr(subprocess, 'run', compile)
    with pytest.raises(ContactsBridgeError) as error:
        bridge._ensure_native_helper()
    assert error.value.error_code == ('HELPER_COMPILE_TIMEOUT' if timeout else 'HELPER_COMPILE_FAILED')
    assert list(build.iterdir()) == []


def test_entitlement_failure_has_specific_code():
    bridge = AppleContactsBridge(Path('/tmp/scripts'))
    assert bridge._map_script_error('Notes cannot be written: special entitlement').error_code == 'CONTACT_NOTE_UNAVAILABLE'


@pytest.mark.parametrize('restore_source', [False, True])
def test_compiles_hashed_snapshot_when_source_changes_during_compile(tmp_path, monkeypatch, restore_source):
    source = tmp_path / 'bridge.swift'
    source.write_bytes(b'old source')
    build = tmp_path / 'build'
    bridge = AppleContactsBridge(tmp_path, helper_source=source, helper_build_dir=build)

    def compile(command, **kwargs):
        if command[0] == CODESIGN:
            return _signed(command)
        snapshot = Path(command[-3])
        assert snapshot != source
        source.write_bytes(b'new source')
        Path(command[-1]).write_bytes(snapshot.read_bytes())
        if restore_source:
            source.write_bytes(b'old source')
        return subprocess.CompletedProcess(command, 0, '', '')

    monkeypatch.setattr(subprocess, 'run', compile)
    if restore_source:
        binary = bridge._ensure_native_helper()
        assert binary.read_bytes() == b'old source'
        assert binary.parent.parent.parent.name == 'Apple Contacts MCP Helper.app'
    else:
        with pytest.raises(ContactsBridgeError) as error:
            bridge._ensure_native_helper()
        assert error.value.error_code == 'HELPER_SOURCE_CHANGED'
        assert list(build.iterdir()) == []


def test_same_bridge_source_versions_execute_correctly_after_both_install(tmp_path, monkeypatch):
    source = tmp_path / 'bridge.swift'
    build = tmp_path / 'build'
    bridge = AppleContactsBridge(tmp_path, helper_source=source, helper_build_dir=build)
    real_run = subprocess.run

    def compile(command, **kwargs):
        if command[0] == CODESIGN:
            return _signed(command)
        executable = Path(command[-1])
        executable.write_bytes(Path(command[-3]).read_bytes())
        executable.chmod(0o755)
        return subprocess.CompletedProcess(command, 0, '', '')

    monkeypatch.setattr(subprocess, 'run', compile)
    source.write_text('#!/bin/sh\necho old\n')
    old = bridge._ensure_native_helper()
    old_inode = old.stat().st_ino
    source.write_text('#!/bin/sh\necho new\n')
    new = bridge._ensure_native_helper()
    assert old != new
    assert real_run([old], capture_output=True, text=True, check=True).stdout.strip() == 'old'
    assert real_run([new], capture_output=True, text=True, check=True).stdout.strip() == 'new'
    assert old.stat().st_ino == old_inode
    assert not list(build.glob('.apple-contacts-bridge-build-*'))


def test_same_source_concurrent_publish_retains_first_winner_inode_and_marker(tmp_path, monkeypatch):
    from apple_mcp_common import native

    source = tmp_path / 'bridge.swift'
    source.write_text('same source')
    build = tmp_path / 'build'
    barrier = Barrier(4)
    lock = Lock()
    compiled = []
    winner = []
    real_rename = native.rename_without_replacement

    def compile(command, **kwargs):
        if command[0] == CODESIGN:
            return _signed(command)
        with lock:
            marker = f'candidate-{len(compiled)}'.encode()
            compiled.append(marker)
        Path(command[-1]).write_bytes(marker)
        barrier.wait(timeout=5)
        return subprocess.CompletedProcess(command, 0, '', '')

    def publish(old, new):
        with lock:
            real_rename(old, new)
            executable = new / 'Apple Contacts MCP Helper.app' / 'Contents' / 'MacOS' / 'apple-contacts-bridge'
            winner.append((executable.stat().st_ino, executable.read_bytes()))

    monkeypatch.setattr(subprocess, 'run', compile)
    monkeypatch.setattr(native, 'rename_without_replacement', publish)
    with ThreadPoolExecutor(max_workers=4) as pool:
        paths = list(pool.map(lambda _: AppleContactsBridge(tmp_path, helper_source=source, helper_build_dir=build)._ensure_native_helper(), range(4)))
    assert len(compiled) == 4
    assert len(winner) == 1
    assert len(set(paths)) == 1
    assert (paths[0].stat().st_ino, paths[0].read_bytes()) == winner[0]
    assert not list(build.glob('.apple-contacts-bridge-build-*'))


def test_native_build_is_a_signed_bundle_with_contacts_usage_description(tmp_path, monkeypatch):
    import plistlib

    source = tmp_path / 'bridge.swift'
    source.write_text('source')
    bridge = AppleContactsBridge(tmp_path, helper_source=source, helper_build_dir=tmp_path / 'build')
    signed = []

    def run(command, **kwargs):
        if command[0] == CODESIGN:
            signed.append(command)
            return _signed(command)
        Path(command[-1]).write_bytes(b'executable')
        return subprocess.CompletedProcess(command, 0, '', '')

    monkeypatch.setattr(subprocess, 'run', run)
    binary = bridge._ensure_native_helper()
    app = binary.parent.parent.parent
    info = plistlib.loads((app / 'Contents' / 'Info.plist').read_bytes())
    assert info['CFBundleIdentifier'] == CONTACTS_HELPER_BUNDLE.bundle_identifier == 'io.github.jonathanrreed.apple-mcps.contacts-bridge'
    assert info['NSContactsUsageDescription'].strip()
    # Signed in the staging directory, before the bundle is published.
    assert len(signed) == 1
    assert signed[0][:-1] == [CODESIGN, '--force', '--sign', '-', '--identifier', 'io.github.jonathanrreed.apple-mcps.contacts-bridge']
    assert signed[0][-1].endswith('/' + app.parent.name + '/Apple Contacts MCP Helper.app')


def test_native_permission_error_keeps_helper_guidance():
    bridge = AppleContactsBridge(Path('/tmp/scripts'), helper_source=Path('/tmp/bridge.swift'), helper_build_dir=Path('/tmp/build'))
    error = bridge._map_script_error(
        '{"error_code":"PERMISSION_DENIED","message":"macOS denied Contacts access to \'Apple Contacts MCP Helper\'.",'
        '"ok":false,"suggestion":"Open System Settings > Privacy & Security > Contacts and turn on \'Apple Contacts MCP Helper\'."}'
    )
    assert error.error_code == 'PERMISSION_DENIED'
    assert 'Apple Contacts MCP Helper' in error.message
    assert error.suggestion.startswith('Open System Settings > Privacy & Security > Contacts')


def test_permission_diagnostic_reports_checked_app_and_guidance(tmp_path, monkeypatch):
    bridge = AppleContactsBridge(tmp_path, helper_source=tmp_path / 'bridge.swift', helper_build_dir=tmp_path)
    payload = {'ok': True, 'accessible': False, 'status': 'denied', 'tcc_client': 'Apple Contacts MCP Helper', 'suggestion': 'Turn it on.'}
    monkeypatch.setattr(bridge, '_run_script', lambda name: payload)
    accessible, error = bridge.permission_diagnostic()
    assert accessible is False
    assert error.error_code == 'PERMISSION_DENIED'
    assert "'Apple Contacts MCP Helper'" in error.message
    assert error.suggestion == 'Turn it on.'
    assert bridge.permission_client == 'Apple Contacts MCP Helper'


def test_health_names_the_app_macos_checks(monkeypatch):
    from apple_contacts_mcp import tools

    class Bridge:
        permission_client = 'Apple Contacts MCP Helper'

        def permission_diagnostic(self):
            return False, ContactsBridgeError('AUTHORIZATION_UNKNOWN', 'Contacts authorization has not been granted.', 'Choose Allow.')

    monkeypatch.setattr(tools, '_bridge', lambda: Bridge())
    health = tools.contacts_health()
    assert health.permission_status == 'unknown'
    assert health.permission_client == 'Apple Contacts MCP Helper'


def test_permission_guide_names_the_helper():
    from apple_contacts_mcp import tools

    guide = tools.contacts_permission_guide()
    assert guide['helper_name'] == 'Apple Contacts MCP Helper'
    assert 'tccutil reset AddressBook io.github.jonathanrreed.apple-mcps.contacts-bridge' in ' '.join(guide['steps'])
