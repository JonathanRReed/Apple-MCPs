import subprocess
from pathlib import Path

import pytest

from apple_contacts_mcp.config import load_settings
from apple_contacts_mcp.contacts_bridge import AppleContactsBridge, ContactsBridgeError, build_bridge


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
