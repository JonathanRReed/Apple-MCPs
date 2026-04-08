from pathlib import Path
from apple_calendar_mcp.calendar_bridge import CalendarBridge, CalendarBridgeError


def test_list_events_normalizes_event_ids(monkeypatch) -> None:
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))

    def fake_run_helper(command: str, *args: str) -> dict[str, object]:
        if command == "calendar-access-status":
            return {"status": "authorized", "can_read_events": True, "can_write_events": True}
        assert command == "list-calendar-events"
        return {
            "items": [
                {
                    "event_id": "event-123",
                    "title": "Planning",
                    "calendar_id": "calendar-1",
                    "calendar_name": "Work",
                    "start": "2026-03-27T10:00:00-05:00",
                    "end": "2026-03-27T10:30:00-05:00",
                    "all_day": False,
                    "location": "Room 1",
                }
            ]
        }

    monkeypatch.setattr(bridge, "_run_helper", fake_run_helper)
    events = bridge.list_events("2026-03-27T10:00:00-05:00", "2026-03-27T10:30:00-05:00", "calendar-1", 10)

    assert len(events) == 1
    assert events[0].event_id == "event-123"
    assert events[0].title == "Planning"


def test_get_event_raises_when_missing(monkeypatch) -> None:
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))

    def fake_run_helper(command: str, *args: str) -> dict[str, object]:
        raise CalendarBridgeError("EVENT_NOT_FOUND", "missing")

    monkeypatch.setattr(bridge, "_run_helper", fake_run_helper)

    try:
        bridge.get_event("event-123")
    except CalendarBridgeError as exc:
        assert exc.error_code == "EVENT_NOT_FOUND"
    else:
        raise AssertionError("Expected CalendarBridgeError")


def test_calendar_access_status_reads_helper_payload(monkeypatch) -> None:
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))

    def fake_run_helper(command: str, *args: str) -> dict[str, object]:
        assert command == "calendar-access-status"
        return {"status": "denied", "can_read_events": False, "can_write_events": False}

    monkeypatch.setattr(bridge, "_run_helper", fake_run_helper)

    payload = bridge.calendar_access_status()

    assert payload["status"] == "denied"


def test_get_event_normalizes_recurrence_and_attendees(monkeypatch) -> None:
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))

    def fake_run_helper(command: str, *args: str) -> dict[str, object]:
        assert command == "get-calendar-event"
        return {
            "event_id": "event-123",
            "title": "Weekly sync",
            "calendar_id": "calendar-1",
            "calendar_name": "Work",
            "start": "2026-03-27T10:00:00-05:00",
            "end": "2026-03-27T10:30:00-05:00",
            "all_day": False,
            "recurrence_rule": {"frequency": "weekly", "interval": 1, "end_date": None},
            "attendees": [{"name": "Alex", "email": "alex@example.com", "status": "accepted"}],
        }

    monkeypatch.setattr(bridge, "_run_helper", fake_run_helper)

    event = bridge.get_event("event-123")

    assert event.recurrence_rule is not None
    assert event.recurrence_rule.frequency == "weekly"
    assert event.attendees is not None
    assert event.attendees[0].email == "alex@example.com"


def test_list_calendars_falls_back_when_helper_permissions_fail(monkeypatch) -> None:
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))

    def fake_run_helper(command: str, *args: str) -> dict[str, object]:
        raise CalendarBridgeError("PERMISSION_DENIED", "blocked")

    def fake_run_jxa(script: str, *args: str, timeout: int | None = None) -> dict[str, object]:
        return {
            "items": [
                {
                    "calendar_id": "Home",
                    "title": "Home",
                    "source_title": None,
                    "color_hex": None,
                    "allows_content_modifications": None,
                }
            ]
        }

    monkeypatch.setattr(bridge, "_run_helper", fake_run_helper)
    monkeypatch.setattr(bridge, "_run_jxa", fake_run_jxa)

    calendars = bridge.list_calendars()

    assert len(calendars) == 1
    assert calendars[0].calendar_id == "Home"
    assert calendars[0].name == "Home"


def test_list_events_falls_back_when_helper_permissions_fail(monkeypatch) -> None:
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))

    def fake_run_helper(command: str, *args: str) -> dict[str, object]:
        raise CalendarBridgeError("HELPER_COMPILE_FAILED", "blocked")

    def fake_run_jxa(script: str, *args: str, timeout: int | None = None) -> dict[str, object]:
        return {
            "items": [
                {
                    "event_id": "fallback-1",
                    "title": "Fallback event",
                    "calendar_id": "Home",
                    "calendar_name": "Home",
                    "start": "2026-03-27T15:00:00+00:00",
                    "end": "2026-03-27T15:30:00+00:00",
                    "all_day": False,
                    "location": "Desk",
                }
            ]
        }

    monkeypatch.setattr(bridge, "_run_helper", fake_run_helper)
    monkeypatch.setattr(bridge, "_run_jxa", fake_run_jxa)

    events = bridge.list_events("2026-03-27T10:00:00-05:00", "2026-03-27T10:30:00-05:00", "Home", 10)

    assert len(events) == 1
    assert events[0].event_id == "fallback-1"
    assert events[0].calendar_name == "Home"


def test_list_events_dedupes_single_calendar_fallback_results(monkeypatch) -> None:
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))

    def fake_run_helper(command: str, *args: str) -> dict[str, object]:
        raise CalendarBridgeError("HELPER_EXECUTION_FAILED", "blocked")

    def fake_run_jxa(script: str, *args: str, timeout: int | None = None) -> dict[str, object]:
        return {
            "items": [
                {
                    "event_id": "dup-1",
                    "title": "Appointment",
                    "calendar_id": "Home",
                    "calendar_name": "Home",
                    "start": "2026-03-27T15:00:00+00:00",
                    "end": "2026-03-27T15:30:00+00:00",
                    "all_day": False,
                    "location": "Desk",
                },
                {
                    "event_id": "dup-1",
                    "title": "Appointment",
                    "calendar_id": "Home",
                    "calendar_name": "Home",
                    "start": "2026-03-27T15:00:00+00:00",
                    "end": "2026-03-27T15:30:00+00:00",
                    "all_day": False,
                    "location": "Desk",
                },
            ]
        }

    monkeypatch.setattr(bridge, "_run_helper", fake_run_helper)
    monkeypatch.setattr(bridge, "_run_jxa", fake_run_jxa)

    events = bridge.list_events("2026-03-27T10:00:00-05:00", "2026-03-27T12:00:00-05:00", "Home", 10)

    assert len(events) == 1
    assert events[0].event_id == "dup-1"


def test_list_events_fallback_uses_configured_timeout(monkeypatch) -> None:
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))
    captured: dict[str, object] = {}

    def fake_run_helper(command: str, *args: str) -> dict[str, object]:
        raise CalendarBridgeError("HELPER_EXECUTION_FAILED", "blocked")

    def fake_run_jxa(script: str, *args: str, timeout: int | None = None) -> dict[str, object]:
        captured["timeout"] = timeout
        return {"items": []}

    monkeypatch.setattr(bridge, "_run_helper", fake_run_helper)
    monkeypatch.setattr(bridge, "_run_jxa", fake_run_jxa)

    bridge.list_events("2026-03-27T10:00:00-05:00", "2026-03-27T12:00:00-05:00", "Home", 10)

    assert captured["timeout"] == CalendarBridge._JXA_TIMEOUT_SECONDS


def test_list_events_aggregates_broad_fallback_by_calendar(monkeypatch) -> None:
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))

    def fake_run_helper(command: str, *args: str) -> dict[str, object]:
        raise CalendarBridgeError("HELPER_EXECUTION_FAILED", "blocked")

    monkeypatch.setattr(bridge, "_run_helper", fake_run_helper)
    monkeypatch.setattr(
        bridge,
        "_fallback_list_calendars",
        lambda: {
            "items": [
                {"calendar_id": "Work", "title": "Work"},
                {"calendar_id": "Personal", "title": "Personal"},
            ]
        },
    )

    def fake_fallback_list_events(start_iso: str, end_iso: str, calendar_id: str | None = None, limit: int = 100) -> dict[str, object]:
        if calendar_id == "Personal":
            raise CalendarBridgeError("APPLESCRIPT_FALLBACK_TIMEOUT", "slow")
        return {
            "items": [
                {
                    "event_id": "work-1",
                    "title": "Launch review",
                    "calendar_id": "Work",
                    "calendar_name": "Work",
                    "start": "2026-03-27T15:00:00+00:00",
                    "end": "2026-03-27T15:30:00+00:00",
                    "all_day": False,
                    "location": None,
                }
            ]
        }

    monkeypatch.setattr(bridge, "_fallback_list_events", fake_fallback_list_events)

    events = bridge.list_events("2026-03-27T10:00:00-05:00", "2026-03-27T12:00:00-05:00", limit=10)

    assert len(events) == 1
    assert events[0].event_id == "work-1"
    assert events[0].calendar_name == "Work"
