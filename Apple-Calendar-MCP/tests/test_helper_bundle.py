import os
import plistlib
import subprocess

import pytest

from apple_calendar_mcp.calendar_bridge import CalendarBridge, CalendarBridgeError
from apple_calendar_mcp.config import load_settings


@pytest.fixture
def helper(tmp_path):
    source = tmp_path / "bridge.swift"
    source.write_text("// test source\n")
    binary = tmp_path / "Calendar.app" / "Contents" / "MacOS" / "apple-calendar-pim-bridge"
    return CalendarBridge(source, binary), binary.parent.parent / "Info.plist"


def _successful_compile(monkeypatch, bridge):
    calls = []

    def compile_helper(command, **kwargs):
        calls.append(command)
        bridge.helper_binary.write_bytes(b"test executable")
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
    info_path.write_bytes(plistlib.dumps({"old": True}))
    os.utime(bridge.helper_binary, (1000, 1000))
    os.utime(bridge.helper_source, (2000, 2000))
    calls = _successful_compile(monkeypatch, bridge)

    bridge._ensure_helper()

    assert len(calls) == 1
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
