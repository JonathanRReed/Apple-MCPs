import os
import plistlib
import subprocess
from pathlib import Path

import pytest

from apple_calendar_mcp.calendar_bridge import CalendarBridge, CalendarBridgeError
from apple_calendar_mcp.config import load_settings
from apple_mcp_common.native import swift_helper_path


@pytest.fixture
def helper(tmp_path):
    source = tmp_path / "bridge.swift"
    source.write_text("// test source\n")
    binary = tmp_path / "Calendar.app" / "Contents" / "MacOS" / "apple-calendar-pim-bridge"
    return CalendarBridge(source, binary), swift_helper_path(source, binary).parent.parent / "Info.plist"


def _successful_compile(monkeypatch, bridge):
    calls = []

    def compile_helper(command, **kwargs):
        calls.append(command)
        Path(command[-1]).write_bytes(b"test executable")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", compile_helper)
    return calls


def test_settings_place_helper_in_app_bundle(monkeypatch, tmp_path):
    monkeypatch.setenv("APPLE_CALENDAR_MCP_HELPER_BUILD_DIR", str(tmp_path))
    load_settings.cache_clear()
    try:
        assert load_settings().helper_binary == (
            tmp_path / "apple-calendar-pim-bridge.app" / "Contents" / "MacOS" / "apple-calendar-pim-bridge"
        )
    finally:
        load_settings.cache_clear()


def test_compile_writes_bundle_identity_and_permission_descriptions(monkeypatch, helper):
    bridge, info_path = helper
    calls = _successful_compile(monkeypatch, bridge)

    bridge._ensure_helper()

    assert len(calls) == 1
    assert info_path.is_file()
    with info_path.open("rb") as stream:
        info = plistlib.load(stream)
    assert info["CFBundleIdentifier"] == "io.github.jonathanrreed.apple-mcps.calendar-pim-bridge"
    assert info["CFBundleExecutable"] == bridge.helper_binary.name
    assert info["CFBundlePackageType"] == "APPL"
    assert info["LSUIElement"] is True
    assert info["LSBackgroundOnly"] is True
    for key in (
        "NSCalendarsUsageDescription", "NSCalendarsFullAccessUsageDescription",
        "NSRemindersUsageDescription", "NSRemindersFullAccessUsageDescription",
    ):
        assert info[key].strip()


def test_complete_fresh_bundle_is_reused(monkeypatch, helper):
    bridge, info_path = helper
    calls = _successful_compile(monkeypatch, bridge)
    bridge._ensure_helper()
    os.utime(bridge.helper_source, (1000, 1000))
    os.utime(bridge.helper_binary, (2000, 2000))
    # Keep this test independent of the successful-compile plist assertion.
    if not info_path.exists():
        info_path.write_bytes(plistlib.dumps({"CFBundleExecutable": bridge.helper_binary.name}))
    calls.clear()

    bridge._ensure_helper()

    assert calls == []


def test_fresh_binary_without_plist_is_rebuilt(monkeypatch, helper):
    bridge, info_path = helper
    bridge.helper_binary.parent.mkdir(parents=True)
    bridge.helper_binary.write_bytes(b"old executable")
    os.utime(bridge.helper_source, (1000, 1000))
    os.utime(bridge.helper_binary, (2000, 2000))
    calls = _successful_compile(monkeypatch, bridge)

    bridge._ensure_helper()

    assert len(calls) == 1
    assert info_path.is_file()


def test_changed_source_rebuilds_helper(monkeypatch, helper):
    bridge, info_path = helper
    bridge.helper_binary.parent.mkdir(parents=True)
    bridge.helper_binary.write_bytes(b"old executable")
    legacy_info_path = bridge.helper_binary.parent.parent / "Info.plist"
    legacy_info_path.write_bytes(plistlib.dumps({"old": True}))
    os.utime(bridge.helper_binary, (1000, 1000))
    os.utime(bridge.helper_source, (2000, 2000))
    calls = _successful_compile(monkeypatch, bridge)

    bridge._ensure_helper()

    assert len(calls) == 1
    assert plistlib.loads(legacy_info_path.read_bytes()) == {"old": True}
    with info_path.open("rb") as stream:
        assert "CFBundleIdentifier" in plistlib.load(stream)


def test_failed_compile_does_not_create_bundle_metadata(monkeypatch, helper):
    bridge, info_path = helper
    monkeypatch.setattr(subprocess, "run", lambda command, **kwargs: subprocess.CompletedProcess(command, 1, "", "compile failed"))

    with pytest.raises(CalendarBridgeError) as error:
        bridge._ensure_helper()

    assert error.value.error_code == "HELPER_COMPILE_FAILED"
    assert not info_path.exists()


def test_missing_swiftc_has_actionable_error(monkeypatch, helper):
    bridge, info_path = helper

    def unavailable(*args, **kwargs):
        raise FileNotFoundError("swiftc")

    monkeypatch.setattr(subprocess, "run", unavailable)
    with pytest.raises(CalendarBridgeError) as error:
        bridge._ensure_helper()

    assert error.value.error_code == "SWIFTC_UNAVAILABLE"
    assert not info_path.exists()


def test_missing_source_has_actionable_error(helper):
    bridge, info_path = helper
    bridge.helper_source.unlink()

    with pytest.raises(CalendarBridgeError) as error:
        bridge._ensure_helper()

    assert error.value.error_code == "HELPER_SOURCE_MISSING"
    assert not info_path.exists()



def test_missing_metadata_is_repaired_without_recompiling_source(monkeypatch, helper):
    bridge, info_path = helper
    calls = _successful_compile(monkeypatch, bridge)
    executable = bridge._ensure_helper()
    info_path.unlink()
    assert bridge._ensure_helper() == executable
    assert len(calls) == 1
    assert plistlib.loads(info_path.read_bytes())["CFBundleExecutable"] == executable.name


def test_old_bundle_survives_package_upgrade_with_older_source_mtime(monkeypatch, helper):
    bridge, old_info = helper
    calls = _successful_compile(monkeypatch, bridge)
    old_executable = bridge._ensure_helper()
    old_metadata = old_info.read_bytes()
    bridge.helper_source.write_text("// new version\n")
    os.utime(bridge.helper_source, (1, 1))
    new_executable = bridge._ensure_helper()
    assert len(calls) == 2
    assert new_executable != old_executable
    assert old_executable.is_file()
    assert old_info.read_bytes() == old_metadata
    assert new_executable.parent.parent != old_info.parent
    assert bridge.helper_available() == (True, True)


def test_execution_uses_the_path_returned_by_ensure(monkeypatch, helper):
    bridge, _ = helper
    selected = bridge.helper_binary.with_name("chosen-version")

    def ensure():
        bridge.helper_binary = bridge.helper_binary.with_name("other-version")
        return selected

    def run(command, **kwargs):
        assert command[0] == str(selected)
        return subprocess.CompletedProcess(command, 0, '{"ok":true}', "")

    monkeypatch.setattr(bridge, "_ensure_helper", ensure)
    monkeypatch.setattr(subprocess, "run", run)
    assert bridge._run_helper("test") == {"ok": True}



def test_public_read_reports_unsupported_cache_with_location_suggestion(monkeypatch, helper):
    import errno

    from apple_calendar_mcp import tools

    bridge, _ = helper

    def compile(command, **kwargs):
        Path(command[-1]).write_bytes(Path(command[-3]).read_bytes())
        return subprocess.CompletedProcess(command, 0, "", "")

    def unsupported(*args):
        raise OSError(errno.ENOTSUP, "filesystem operation unavailable")

    monkeypatch.setattr("apple_mcp_common.native.subprocess.run", compile)
    monkeypatch.setattr("apple_mcp_common.native.os.link", unsupported)
    monkeypatch.setattr("apple_mcp_common.native.rename_without_replacement", unsupported)
    monkeypatch.setattr(tools, "_bridge", lambda: bridge)
    result = tools.calendar_list_calendars()
    assert result.ok is False
    assert result.error.error_code == "HELPER_CACHE_INSTALL_FAILED"
    assert "helper build directory" in result.error.suggestion
    assert not list(bridge.helper_source.parent.rglob(".*"))
