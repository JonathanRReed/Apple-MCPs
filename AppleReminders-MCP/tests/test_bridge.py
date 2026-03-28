from pathlib import Path

from apple_reminders_mcp.reminders_bridge import RemindersBridge, RemindersBridgeError


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
