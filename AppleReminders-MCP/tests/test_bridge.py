import subprocess
from pathlib import Path

import pytest

from apple_reminders_mcp.reminders_bridge import RemindersBridge, RemindersBridgeError


@pytest.mark.parametrize("deleted", [True, False])
def test_delete_list_maps_swift_object_id(monkeypatch, deleted) -> None:
    bridge = RemindersBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))

    def fake_run_helper(command: str, *args: str) -> dict[str, object]:
        assert command == "delete-reminder-list"
        assert args == ("list-qa",)
        return {"deleted": deleted, "object_id": "list-qa"}

    monkeypatch.setattr(bridge, "_run_helper", fake_run_helper)
    result = bridge.delete_list("list-qa")
    assert result.ok is True
    assert result.list_id == "list-qa"
    assert result.deleted is deleted


def test_list_lists_normalizes_payload(monkeypatch) -> None:
    bridge = RemindersBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))

    def fake_run_helper(command: str, *args: str) -> dict[str, object]:
        assert command == "list-reminder-lists"
        return {
            "items": [
                {
                    "list_id": "list-1",
                    "title": "Chores",
                    "source_title": "iCloud",
                    "allows_content_modifications": True,
                    "color_hex": "#D9A69F",
                }
            ]
        }

    monkeypatch.setattr(bridge, "_run_helper", fake_run_helper)
    lists = bridge.list_lists()

    assert len(lists) == 1
    assert lists[0].title == "Chores"


def test_get_reminder_maps_not_found(monkeypatch) -> None:
    bridge = RemindersBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))

    def fake_run_helper(command: str, *args: str) -> dict[str, object]:
        raise RemindersBridgeError("REMINDER_NOT_FOUND", "missing")

    monkeypatch.setattr(bridge, "_run_helper", fake_run_helper)

    try:
        bridge.get_reminder("x-apple-reminder://missing")
    except RemindersBridgeError as exc:
        assert exc.error_code == "REMINDER_NOT_FOUND"
    else:
        raise AssertionError("Expected RemindersBridgeError")


def test_create_reminder_rejects_subtask_parent(monkeypatch) -> None:
    bridge = RemindersBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))

    try:
        bridge.create_reminder(title="Child", list_id="list-1", parent_reminder_id="x-apple-reminder://parent")
    except RemindersBridgeError as exc:
        assert exc.error_code == "SUBTASKS_UNSUPPORTED"
    else:
        raise AssertionError("Expected RemindersBridgeError")



def test_execution_uses_the_path_returned_by_ensure(monkeypatch, tmp_path):
    bridge = RemindersBridge(tmp_path / "source.swift", tmp_path / "helper")
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



def test_public_read_reports_unsupported_cache_with_location_suggestion(monkeypatch, tmp_path):
    import errno

    from apple_reminders_mcp import tools

    source = tmp_path / "source.swift"
    source.write_text("owned fixture")
    bridge = RemindersBridge(source, tmp_path / "helper")

    def compile(command, **kwargs):
        Path(command[-1]).write_bytes(Path(command[-3]).read_bytes())
        return subprocess.CompletedProcess(command, 0, "", "")

    def unsupported(*args):
        raise OSError(errno.ENOTSUP, "filesystem operation unavailable")

    monkeypatch.setattr("apple_mcp_common.native.subprocess.run", compile)
    monkeypatch.setattr("apple_mcp_common.native.os.link", unsupported)
    monkeypatch.setattr("apple_mcp_common.native.rename_without_replacement", unsupported)
    monkeypatch.setattr(tools, "_bridge", lambda: bridge)
    result = tools.reminders_list_lists()
    assert result.ok is False
    assert result.error.error_code == "HELPER_CACHE_INSTALL_FAILED"
    assert "helper build directory" in result.error.suggestion
    assert not list(bridge.helper_source.parent.rglob(".*"))
