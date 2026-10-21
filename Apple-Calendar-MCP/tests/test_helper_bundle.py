import plistlib
import subprocess
from pathlib import Path

import pytest

from apple_calendar_mcp.calendar_bridge import CALENDAR_HELPER_BUNDLE, CalendarBridge, CalendarBridgeError
from apple_calendar_mcp.config import load_settings
from apple_mcp_common.native import CODESIGN, helper_bundle_executable


@pytest.fixture
def bridge(tmp_path):
    source = tmp_path / "bridge.swift"
    source.write_text("// test source\n")
    return CalendarBridge(source, tmp_path / "build")


def _successful_build(monkeypatch):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if command[0] != CODESIGN:
            Path(command[-1]).write_bytes(b"test executable")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    return calls


def test_settings_use_build_dir_from_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("APPLE_CALENDAR_MCP_HELPER_BUILD_DIR", str(tmp_path))
    load_settings.cache_clear()
    try:
        assert load_settings().helper_build_dir == tmp_path
    finally:
        load_settings.cache_clear()


def test_build_is_a_signed_bundle_with_stable_identity_and_usage_descriptions(monkeypatch, bridge):
    calls = _successful_build(monkeypatch)

    executable = bridge._ensure_helper()

    app = executable.parent.parent.parent
    assert app.name == "Apple Calendar MCP Helper.app"
    assert executable.name == "apple-calendar-pim-bridge"
    info = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
    # Unchanged from earlier releases, so existing grants keyed by bundle id still match.
    assert info["CFBundleIdentifier"] == "io.github.jonathanrreed.apple-mcps.calendar-pim-bridge"
    assert info["CFBundleExecutable"] == executable.name
    assert info["CFBundlePackageType"] == "APPL"
    assert info["LSUIElement"] is True
    for key in (
        "NSCalendarsUsageDescription", "NSCalendarsFullAccessUsageDescription",
        "NSRemindersUsageDescription", "NSRemindersFullAccessUsageDescription",
    ):
        assert info[key].strip()
    swiftc, codesign = calls
    assert swiftc[0] == "swiftc"
    assert codesign[:-1] == [CODESIGN, "--force", "--sign", "-", "--identifier", CALENDAR_HELPER_BUNDLE.bundle_identifier]
    assert codesign[-1].endswith("/Apple Calendar MCP Helper.app")
    assert bridge.helper_binary == executable


def test_built_bundle_is_reused_and_reported_available(monkeypatch, bridge):
    calls = _successful_build(monkeypatch)
    assert bridge.helper_available() == (True, False)
    first = bridge._ensure_helper()
    calls.clear()

    assert bridge._ensure_helper() == first
    assert calls == []
    assert bridge.helper_available() == (True, True)
    assert helper_bundle_executable(bridge.helper_source, bridge.helper_build_dir, CALENDAR_HELPER_BUNDLE) == first


def test_old_bundle_survives_package_upgrade(monkeypatch, bridge):
    _successful_build(monkeypatch)
    old_executable = bridge._ensure_helper()
    bridge.helper_source.write_text("// new version\n")

    new_executable = bridge._ensure_helper()

    assert new_executable != old_executable
    assert old_executable.is_file()
    assert new_executable.is_file()


def test_failed_compile_does_not_publish_a_bundle(monkeypatch, bridge):
    monkeypatch.setattr(subprocess, "run", lambda command, **kwargs: subprocess.CompletedProcess(command, 1, "", "compile failed"))

    with pytest.raises(CalendarBridgeError) as error:
        bridge._ensure_helper()

    assert error.value.error_code == "HELPER_COMPILE_FAILED"
    assert list(bridge.helper_build_dir.iterdir()) == []


def test_missing_swiftc_has_actionable_error(monkeypatch, bridge):
    def unavailable(*args, **kwargs):
        raise FileNotFoundError("swiftc")

    monkeypatch.setattr(subprocess, "run", unavailable)
    with pytest.raises(CalendarBridgeError) as error:
        bridge._ensure_helper()

    assert error.value.error_code == "SWIFTC_UNAVAILABLE"


def test_missing_source_has_actionable_error(bridge):
    bridge.helper_source.unlink()

    with pytest.raises(CalendarBridgeError) as error:
        bridge._ensure_helper()

    assert error.value.error_code == "HELPER_SOURCE_MISSING"


def test_execution_uses_the_path_returned_by_ensure(monkeypatch, bridge, tmp_path):
    selected = tmp_path / "chosen-version"

    def ensure():
        bridge.helper_binary = tmp_path / "other-version"
        return selected

    def run(command, **kwargs):
        assert command[0] == str(selected)
        return subprocess.CompletedProcess(command, 0, '{"ok":true}', "")

    monkeypatch.setattr(bridge, "_ensure_helper", ensure)
    monkeypatch.setattr(subprocess, "run", run)
    assert bridge._run_helper("test") == {"ok": True}


def test_public_read_reports_unsupported_cache_with_location_suggestion(monkeypatch, bridge):
    import errno

    from apple_calendar_mcp import tools

    def compile(command, **kwargs):
        if command[0] != CODESIGN:
            Path(command[-1]).write_bytes(Path(command[-3]).read_bytes())
        return subprocess.CompletedProcess(command, 0, "", "")

    def unsupported(*args):
        raise OSError(errno.ENOTSUP, "filesystem operation unavailable")

    monkeypatch.setattr("apple_mcp_common.native.subprocess.run", compile)
    monkeypatch.setattr("apple_mcp_common.native.rename_without_replacement", unsupported)
    monkeypatch.setattr(tools, "_bridge", lambda: bridge)
    result = tools.calendar_list_calendars()
    assert result.ok is False
    assert result.error.error_code == "HELPER_CACHE_INSTALL_FAILED"
    assert "helper build directory" in result.error.suggestion
    assert not list(bridge.helper_source.parent.rglob(".*"))


def test_permission_guide_names_the_helper_and_the_reset_command():
    from apple_calendar_mcp import tools

    guide = tools.calendar_permission_guide()
    text = " ".join(guide["steps"] + guide["notes"])
    assert guide["helper_name"] == "Apple Calendar MCP Helper"
    assert "System Settings > Privacy & Security > Calendars" in text
    assert "tccutil reset Calendar io.github.jonathanrreed.apple-mcps.calendar-pim-bridge" in text
    assert "usage description" in text
