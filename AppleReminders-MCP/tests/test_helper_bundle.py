import plistlib
import subprocess
from pathlib import Path

import pytest

from apple_mcp_common.native import CODESIGN
from apple_reminders_mcp import tools
from apple_reminders_mcp.config import load_settings
from apple_reminders_mcp.reminders_bridge import REMINDERS_HELPER_BUNDLE, RemindersBridge, RemindersBridgeError


@pytest.fixture
def bridge(tmp_path):
    source = tmp_path / "bridge.swift"
    source.write_text("// test source\n")
    return RemindersBridge(source, tmp_path / "build")


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
    monkeypatch.setenv("APPLE_REMINDERS_MCP_HELPER_BUILD_DIR", str(tmp_path))
    load_settings.cache_clear()
    try:
        assert load_settings().helper_build_dir == tmp_path
    finally:
        load_settings.cache_clear()


def test_helper_is_built_as_a_signed_bundle_not_a_bare_binary(monkeypatch, bridge):
    calls = _successful_build(monkeypatch)

    executable = bridge._ensure_helper()

    app = executable.parent.parent.parent
    assert app.name == "Apple Reminders MCP Helper.app"
    assert executable.relative_to(app) == Path("Contents/MacOS/apple-reminders-pim-bridge")
    info = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
    assert info["CFBundleIdentifier"] == "io.github.jonathanrreed.apple-mcps.reminders-pim-bridge"
    assert info["CFBundleExecutable"] == "apple-reminders-pim-bridge"
    assert info["NSRemindersUsageDescription"].strip()
    assert info["NSRemindersFullAccessUsageDescription"].strip()
    assert calls[-1][:-1] == [CODESIGN, "--force", "--sign", "-", "--identifier", REMINDERS_HELPER_BUNDLE.bundle_identifier]
    assert bridge.helper_available() == (True, True)


def test_access_status_reads_without_requesting(monkeypatch, bridge):
    seen = []

    def run(command, **kwargs):
        seen.append(command[1:])
        return subprocess.CompletedProcess(command, 0, '{"ok":true,"status":"not_determined"}', "")

    monkeypatch.setattr(bridge, "_ensure_helper", lambda: Path("/tmp/helper"))
    monkeypatch.setattr(subprocess, "run", run)

    assert bridge.access_status()["status"] == "not_determined"
    assert seen == [["reminders-access-status"]]


def test_permission_denied_passes_helper_guidance_through(monkeypatch, bridge):
    payload = (
        '{"ok":false,"error_code":"PERMISSION_DENIED","message":"macOS denied Reminders access to \'Apple Reminders MCP Helper\'.",'
        '"suggestion":"Open System Settings > Privacy & Security > Reminders and turn on \'Apple Reminders MCP Helper\'."}'
    )
    monkeypatch.setattr(bridge, "_ensure_helper", lambda: Path("/tmp/helper"))
    monkeypatch.setattr(subprocess, "run", lambda command, **kwargs: subprocess.CompletedProcess(command, 1, payload, ""))

    with pytest.raises(RemindersBridgeError) as error:
        bridge.list_lists()

    assert error.value.error_code == "PERMISSION_DENIED"
    assert "Apple Reminders MCP Helper" in error.value.message
    assert "Privacy & Security > Reminders" in error.value.suggestion


class _StatusBridge:
    def __init__(self, payload=None, error=None):
        self.payload, self.error = payload, error

    def helper_available(self):
        return True, True

    def access_status(self):
        if self.error is not None:
            raise self.error
        return self.payload


def test_health_reports_access_and_the_app_macos_checks(monkeypatch):
    payload = {
        "ok": True, "domain": "reminders", "status": "denied", "can_read_events": False, "can_write_events": False,
        "message": "macOS has not granted Reminders access to Apple Reminders MCP Helper.",
        "suggestion": "Open System Settings > Privacy & Security > Reminders and turn on 'Apple Reminders MCP Helper'.",
        "tcc_client": "Apple Reminders MCP Helper", "helper_is_responsible": True,
    }
    monkeypatch.setattr(tools, "_bridge", lambda: _StatusBridge(payload))

    health = tools.reminders_health()

    assert health.access_status == "denied"
    assert health.can_access_reminders is False
    assert health.permission_client == "Apple Reminders MCP Helper"
    assert "Privacy & Security > Reminders" in health.permission_suggestion


def test_health_reports_granted_access(monkeypatch):
    payload = {"ok": True, "status": "full_access", "can_read_events": True, "can_write_events": True, "tcc_client": "Terminal"}
    monkeypatch.setattr(tools, "_bridge", lambda: _StatusBridge(payload))

    health = tools.reminders_health()

    assert health.access_status == "full_access"
    assert health.can_access_reminders is True
    assert health.permission_error is None


def test_health_survives_helper_errors(monkeypatch):
    error = RemindersBridgeError("SWIFTC_UNAVAILABLE", "Could not run swiftc.", "Install Xcode Command Line Tools.")
    monkeypatch.setattr(tools, "_bridge", lambda: _StatusBridge(error=error))

    health = tools.reminders_health()

    assert health.ok is True
    assert health.access_status == "helper_error"
    assert health.permission_suggestion == "Install Xcode Command Line Tools."


def test_permission_guide_names_the_helper_and_the_reset_command():
    guide = tools.reminders_permission_guide()
    text = " ".join(guide["steps"] + guide["notes"])
    assert guide["helper_name"] == "Apple Reminders MCP Helper"
    assert "System Settings > Privacy & Security > Reminders" in text
    assert "tccutil reset Reminders io.github.jonathanrreed.apple-mcps.reminders-pim-bridge" in text
