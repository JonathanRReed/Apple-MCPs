import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import quote, unquote

import pytest

from apple_calendar_mcp.calendar_bridge import CalendarBridge, CalendarBridgeError

_EVENT_PAYLOAD = {
    "event_id": "event-123",
    "title": "Planning",
    "calendar_id": "calendar-1",
    "calendar_name": "Work",
    "start": "2026-03-27T10:00:00-05:00",
    "end": "2026-03-27T10:30:00-05:00",
    "all_day": False,
}


def _capture_bridge(monkeypatch, captured: dict[str, object], response: dict[str, object] | None = None) -> CalendarBridge:
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))

    def fake_run_helper(command: str, *args: str) -> dict[str, object]:
        captured["command"] = command
        captured["request"] = json.loads(args[-1])
        return {**_EVENT_PAYLOAD, **(response or {})}

    monkeypatch.setattr(bridge, "_run_helper", fake_run_helper)
    return bridge


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
    # EVENT_NOT_FOUND from the native helper now also retries through the JXA
    # fallback (see test_get_event_falls_back_on_event_not_found below): under
    # write-only Calendar access, EVERY id the caller ever saw came from that
    # same fallback, so the native helper can never resolve one by identifier
    # and would otherwise always raise a misleading EVENT_NOT_FOUND. A genuine
    # miss must still surface as EVENT_NOT_FOUND once the fallback also fails.
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))

    def fake_run_helper(command: str, *args: str) -> dict[str, object]:
        raise CalendarBridgeError("EVENT_NOT_FOUND", "missing")

    def fake_run_jxa(script: str, *args: str, timeout: int | None = None) -> dict[str, object]:
        return {"__error__": "EVENT_NOT_FOUND"}

    monkeypatch.setattr(bridge, "_run_helper", fake_run_helper)
    monkeypatch.setattr(bridge, "_run_jxa", fake_run_jxa)

    try:
        bridge.get_event("event-123")
    except CalendarBridgeError as exc:
        assert exc.error_code == "EVENT_NOT_FOUND"
    else:
        raise AssertionError("Expected CalendarBridgeError")


def test_get_event_falls_back_on_event_not_found(monkeypatch) -> None:
    # The concrete bug this closes: under write-only Calendar access, ids
    # only ever come from the JXA read fallback (a calendar NAME plus the
    # AppleScript event uid), so store.event(withIdentifier:) in the native
    # Swift helper can never resolve them and always raises EVENT_NOT_FOUND,
    # even for an id that is perfectly valid in the fallback's own world.
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))

    def fake_run_helper(command: str, *args: str) -> dict[str, object]:
        raise CalendarBridgeError("EVENT_NOT_FOUND", "missing")

    def fake_run_jxa(script: str, *args: str, timeout: int | None = None) -> dict[str, object]:
        return {
            "event_id": "applescript-uid-1",
            "title": "Fallback event",
            "calendar_id": "Home",
            "calendar_name": "Home",
            "start": "2026-03-27T15:00:00+00:00",
            "end": "2026-03-27T15:30:00+00:00",
            "all_day": False,
            "location": None,
            "notes": None,
        }

    monkeypatch.setattr(bridge, "_run_helper", fake_run_helper)
    monkeypatch.setattr(bridge, "_run_jxa", fake_run_jxa)

    event = bridge.get_event("applescript-uid-1")

    assert event.event_id == "applescript-uid-1"
    assert event.calendar_name == "Home"


def test_create_event_falls_back_when_calendar_id_is_a_name(monkeypatch) -> None:
    # The exact repro Robin hit: create_event("Privat", ...) fails natively
    # with CALENDAR_NOT_FOUND because "Privat" is a calendar NAME from the
    # JXA list fallback, not a real EKCalendar.calendarIdentifier.
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))

    def fake_run_helper(command: str, *args: str) -> dict[str, object]:
        raise CalendarBridgeError("CALENDAR_NOT_FOUND", "No calendar matched 'Privat'.")

    def fake_run_jxa(script: str, *args: str, timeout: int | None = None) -> dict[str, object]:
        return {
            "event_id": "new-uid-1",
            "title": args[1],
            "calendar_id": args[0],
            "calendar_name": args[0],
            "start": "2028-06-01T09:00:00+00:00",
            "end": "2028-06-01T09:30:00+00:00",
            "all_day": False,
            "location": None,
            "notes": None,
        }

    monkeypatch.setattr(bridge, "_run_helper", fake_run_helper)
    monkeypatch.setattr(bridge, "_run_jxa", fake_run_jxa)

    event = bridge.create_event(
        title="Telekom pruefen",
        calendar_id="Privat",
        start_iso="2028-06-01T09:00:00Z",
        end_iso="2028-06-01T09:30:00Z",
    )

    assert event.event_id == "new-uid-1"
    assert event.calendar_id == "Privat"


def test_delete_event_falls_back_on_event_not_found(monkeypatch) -> None:
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))

    def fake_run_helper(command: str, *args: str) -> dict[str, object]:
        raise CalendarBridgeError("EVENT_NOT_FOUND", "missing")

    def fake_run_jxa(script: str, *args: str, timeout: int | None = None) -> dict[str, object]:
        return {"deleted": True}

    monkeypatch.setattr(bridge, "_run_helper", fake_run_helper)
    monkeypatch.setattr(bridge, "_run_jxa", fake_run_jxa)

    assert bridge.delete_event("applescript-uid-1") is True


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


_BATCH_EVENT = {
    "event_id": "event-123",
    "title": "Planning",
    "calendar_id": "calendar-1",
    "calendar_name": "Work",
    "start": "2026-03-27T10:00:00-05:00",
    "end": "2026-03-27T10:30:00-05:00",
    "all_day": False,
    "location": "Room 1",
}


def _batch_bridge(monkeypatch, captured, payload):
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))

    def fake_run_helper(command: str, *args: str) -> dict[str, object]:
        if command == "get-calendar-event":
            raise CalendarBridgeError("EVENT_NOT_FOUND", "explicit mocked native miss")
        captured["command"] = command
        captured["request"] = json.loads(args[0]) if args else None
        return payload

    def missing_fallback(event_id):
        raise CalendarBridgeError("EVENT_NOT_FOUND", "explicit mocked fallback miss")

    monkeypatch.setattr(bridge, "_run_helper", fake_run_helper)
    monkeypatch.setattr(bridge, "_fallback_get_event", missing_fallback)
    return bridge


def test_get_events_sends_one_request_for_every_id(monkeypatch) -> None:
    captured: dict[str, object] = {}
    bridge = _batch_bridge(monkeypatch, captured, {
        "count": 1,
        "items": [{"event_id": "event-123", "found": True, "event": _BATCH_EVENT}],
    })

    resolved = bridge.get_events(["event-123"])

    assert captured["command"] == "get-calendar-events"
    assert captured["request"] == {"event_ids": ["event-123"]}
    assert resolved["event-123"].title == "Planning"


def test_get_events_maps_a_reported_miss_to_none(monkeypatch) -> None:
    captured: dict[str, object] = {}
    bridge = _batch_bridge(monkeypatch, captured, {
        "count": 2,
        "items": [
            {"event_id": "event-123", "found": True, "event": _BATCH_EVENT},
            {"event_id": "gone-1", "found": False, "error_code": "EVENT_NOT_FOUND"},
        ],
    })

    resolved = bridge.get_events(["event-123", "gone-1"])

    assert resolved["event-123"] is not None
    assert resolved["gone-1"] is None


def test_get_events_omits_ids_the_helper_did_not_answer_for(monkeypatch) -> None:
    """Absence must not read as "gone". A caller that deletes a stored mapping
    on not-found has to be able to tell a positive miss from a non-answer."""
    captured: dict[str, object] = {}
    bridge = _batch_bridge(monkeypatch, captured, {
        "count": 1,
        "items": [{"event_id": "event-123", "found": True, "event": _BATCH_EVENT}],
    })

    resolved = bridge.get_events(["event-123", "never-mentioned"])

    assert "never-mentioned" not in resolved


def test_get_events_omits_unrecognized_entry_shapes(monkeypatch) -> None:
    captured: dict[str, object] = {}
    bridge = _batch_bridge(monkeypatch, captured, {
        "count": 2,
        "items": [
            {"event_id": "a", "found": True},                             # no event
            {"event_id": "b", "found": False, "error_code": "SOMETHING"},  # unknown code
        ],
    })

    assert bridge.get_events(["a", "b"]) == {}


def test_get_events_makes_no_call_for_an_empty_list(monkeypatch) -> None:
    captured: dict[str, object] = {}
    bridge = _batch_bridge(monkeypatch, captured, {"count": 0, "items": []})

    assert bridge.get_events([]) == {}
    assert captured == {}


# The JXA update fallback assigns startDate and endDate one at a time, and
# Calendar.app validates after every single assignment. Moving an event later
# in the day used to write the new start while the old end was still in place,
# which is start > end, and Calendar rejected the whole update with -10025
# ("Das Anfangsdatum muss vor dem Enddatum liegen"). The two tests below run
# the JavaScript the bridge really generates against a Calendar.app stub that
# reproduces that validation, so a regression fails here instead of on a live
# calendar.
_JXA_CALENDAR_STUB = """
function makeEvent(uid, title, start, end) {
  const evt = {
    _uid: uid, _summary: title, _start: start, _end: end,
    _location: "", _description: "", _allday: false,
    uid: function () { return evt._uid; },
    delete: function () { throw new Error("unexpected delete"); }
  };
  const validate = function (start, end) {
    if (start >= end) {
      throw new Error("Failed to save event, with error [start date must be before end date] (-10025)");
    }
  };
  Object.defineProperty(evt, "startDate", {
    get: function () { return function () { return evt._start; }; },
    set: function (value) { validate(value, evt._end); evt._start = value; }
  });
  Object.defineProperty(evt, "endDate", {
    get: function () { return function () { return evt._end; }; },
    set: function (value) { validate(evt._start, value); evt._end = value; }
  });
  Object.defineProperty(evt, "summary", {
    get: function () { return function () { return evt._summary; }; },
    set: function (value) { evt._summary = value; }
  });
  Object.defineProperty(evt, "location", {
    get: function () { return function () { return evt._location; }; },
    set: function (value) { evt._location = value; }
  });
  Object.defineProperty(evt, "description", {
    get: function () { return function () { return evt._description; }; },
    set: function (value) { evt._description = value; }
  });
  Object.defineProperty(evt, "alldayEvent", {
    get: function () { return function () { return evt._allday; }; },
    set: function (value) { evt._allday = value; }
  });
  return evt;
}

const STUB_EVENT = makeEvent(
  "event-1", "Standup", new Date("2026-03-27T13:30:00Z"), new Date("2026-03-27T14:30:00Z")
);

const STUB_CALENDAR = {
  name: function () { return "Work"; },
  events: {
    whose: function (query) {
      return function () {
        return STUB_EVENT.uid() === query.uid ? [STUB_EVENT] : [];
      };
    },
    push: function () { throw new Error("unexpected push"); }
  }
};

function Application() {
  const calendars = function () { return [STUB_CALENDAR]; };
  calendars.byName = function (name) { return name === "Work" ? STUB_CALENDAR : null; };
  return {calendars: calendars, Event: function () { throw new Error("unexpected Event()"); }};
}
"""


def _run_jxa_update_in_node(script: str, event_id: str, fields_json: str) -> dict[str, object]:
    node = shutil.which("node")
    if node is None:  # pragma: no cover - depends on the developer machine
        pytest.skip("node is required to execute the generated JXA update script")

    harness = _JXA_CALENDAR_STUB + script + "\nconsole.log(run(process.argv.slice(2)));\n"
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as handle:
        handle.write(harness)
        harness_path = handle.name
    completed = subprocess.run(
        [node, harness_path, event_id, fields_json],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout.strip())


def test_update_event_fallback_moves_event_later_without_invalid_intermediate_state(monkeypatch) -> None:
    # The reproduced bug: the new start (17:00) is after the OLD end (14:30).
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))
    captured: dict[str, str] = {}

    def fake_run_jxa(script: str, *args: str, timeout: int | None = None) -> dict[str, object]:
        captured["script"] = script
        return _run_jxa_update_in_node(script, args[0], args[1])

    monkeypatch.setattr(bridge, "_run_jxa", fake_run_jxa)

    payload = bridge._fallback_update_event(
        "event-1",
        title=None,
        calendar_id=None,
        start_iso="2026-03-27T17:00:00Z",
        end_iso="2026-03-27T18:00:00Z",
        notes=None,
        location=None,
        all_day=None,
    )

    assert payload["start"] == "2026-03-27T17:00:00.000Z"
    assert payload["end"] == "2026-03-27T18:00:00.000Z"


def test_update_event_fallback_moves_event_earlier_without_invalid_intermediate_state(monkeypatch) -> None:
    # The mirrored case: the new end (12:30) is before the OLD start (13:30).
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))

    def fake_run_jxa(script: str, *args: str, timeout: int | None = None) -> dict[str, object]:
        return _run_jxa_update_in_node(script, args[0], args[1])

    monkeypatch.setattr(bridge, "_run_jxa", fake_run_jxa)

    payload = bridge._fallback_update_event(
        "event-1",
        title=None,
        calendar_id=None,
        start_iso="2026-03-27T11:30:00Z",
        end_iso="2026-03-27T12:30:00Z",
        notes=None,
        location=None,
        all_day=None,
    )

    assert payload["start"] == "2026-03-27T11:30:00.000Z"
    assert payload["end"] == "2026-03-27T12:30:00.000Z"


def test_update_event_fallback_keeps_working_for_overlapping_and_single_bound_moves(monkeypatch) -> None:
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))

    def fake_run_jxa(script: str, *args: str, timeout: int | None = None) -> dict[str, object]:
        return _run_jxa_update_in_node(script, args[0], args[1])

    monkeypatch.setattr(bridge, "_run_jxa", fake_run_jxa)

    def update(start_iso: str | None, end_iso: str | None) -> dict[str, object]:
        return bridge._fallback_update_event(
            "event-1",
            title=None,
            calendar_id=None,
            start_iso=start_iso,
            end_iso=end_iso,
            notes=None,
            location=None,
            all_day=None,
        )

    overlapping = update("2026-03-27T14:00:00Z", "2026-03-27T15:00:00Z")
    assert overlapping["start"] == "2026-03-27T14:00:00.000Z"
    assert overlapping["end"] == "2026-03-27T15:00:00.000Z"

    start_only = update("2026-03-27T14:00:00Z", None)
    assert start_only["start"] == "2026-03-27T14:00:00.000Z"
    assert start_only["end"] == "2026-03-27T14:30:00.000Z"

    end_only = update(None, "2026-03-27T16:00:00Z")
    assert end_only["start"] == "2026-03-27T13:30:00.000Z"
    assert end_only["end"] == "2026-03-27T16:00:00.000Z"

@pytest.mark.parametrize("event_ids", ["abc", b"abc", {"a"}, {"a": True}, None, 42, [""] , ["  "], ["a", None], ["a", 1]])
def test_batch_rejects_invalid_ids_before_lookup(monkeypatch, event_ids) -> None:
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))

    def unexpected(*args):
        raise AssertionError("invalid input must not reach a helper")

    monkeypatch.setattr(bridge, "_run_helper", unexpected)
    with pytest.raises(CalendarBridgeError) as failure:
        bridge.get_events(event_ids)
    assert failure.value.error_code == "INVALID_INPUT"


def test_batch_rejects_oversized_input_before_any_lookup(monkeypatch) -> None:
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))

    def unexpected(*args):
        raise AssertionError("oversized input must not reach a helper")

    monkeypatch.setattr(bridge, "_run_helper", unexpected)
    for ids in (["a"] * 10001, ["small", "a" * 32768], ["small", "😀" * 3000]):
        with pytest.raises(CalendarBridgeError) as failure:
            bridge.get_events(ids)
        assert failure.value.error_code == "INVALID_INPUT"


@pytest.mark.parametrize("items", [
    None, {}, "items", [None], [42], [["not", "an", "object"]],
    [{"event_id": ["a"], "found": False, "error_code": "EVENT_NOT_FOUND"}],
    [{"event_id": "a", "error_code": "EVENT_NOT_FOUND"}],
    [{"event_id": "a", "found": 0, "error_code": "EVENT_NOT_FOUND"}],
    [{"event_id": "a", "found": 1, "event": {**_BATCH_EVENT, "event_id": "a"}}],
    [{"event_id": "a", "found": False, "error_code": "EVENT_NOT_FOUND", "event": {}}],
    [{"event_id": "a", "found": True, "event": {"event_id": "a"}}],
    [{"event_id": "a", "found": True, "event": {**_BATCH_EVENT, "event_id": "a", "all_day": "false"}}],
    [{"event_id": "a", "found": True, "error_code": "EVENT_NOT_FOUND", "event": {**_BATCH_EVENT, "event_id": "a"}}],
    [{"event_id": "unrequested", "found": False, "error_code": "EVENT_NOT_FOUND"}],
])
def test_batch_unanswered_or_malformed_entries_stay_unknown(monkeypatch, items) -> None:
    bridge = _batch_bridge(monkeypatch, {}, {"items": items})

    def unexpected(event_id):
        raise AssertionError("malformed entry must not trigger an absence-confirming lookup")

    monkeypatch.setattr(bridge, "get_event", unexpected)
    assert bridge.get_events(["a"]) == {}


@pytest.mark.parametrize("entries", [
    [
        {"event_id": "a", "found": True, "event": {**_BATCH_EVENT, "event_id": "a"}},
        {"event_id": "a", "found": False, "error_code": "EVENT_NOT_FOUND"},
    ],
    [
        {"event_id": "a", "found": False, "error_code": "EVENT_NOT_FOUND"},
        {"event_id": "a", "found": True, "event": {**_BATCH_EVENT, "event_id": "a"}},
    ],
    [
        {"event_id": "a", "found": False, "error_code": "EVENT_NOT_FOUND"},
        {"event_id": "a", "found": False, "error_code": "EVENT_NOT_FOUND"},
    ],
    [
        {"event_id": "a", "found": True, "event": {**_BATCH_EVENT, "event_id": "a"}},
        {"event_id": "a"},
    ],
])
def test_batch_duplicate_results_stay_unknown(monkeypatch, entries) -> None:
    bridge = _batch_bridge(monkeypatch, {}, {"items": entries})
    assert bridge.get_events(["a"]) == {}


@pytest.mark.parametrize("event_id", ["applescript::Work::2026-03-27T10:00:00Z::Planning", "jxa-uid-1"])
def test_batch_preserves_live_jxa_identifier_like_single_get(monkeypatch, event_id) -> None:
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))
    live = {**_BATCH_EVENT, "event_id": event_id}
    calls = []

    def native(command, *args):
        calls.append(command)
        if command == "get-calendar-events":
            return {"items": [{"event_id": event_id, "found": False, "error_code": "EVENT_NOT_FOUND"}]}
        raise CalendarBridgeError("EVENT_NOT_FOUND", "native identifiers do not resolve JXA IDs")

    monkeypatch.setattr(bridge, "_run_helper", native)
    monkeypatch.setattr(bridge, "_fallback_get_event", lambda requested: dict(live))

    single = bridge.get_event(event_id)
    batch = bridge.get_events([event_id])

    assert batch[event_id].model_dump() == single.model_dump()
    if event_id.startswith("applescript::"):
        assert "get-calendar-events" not in calls


def test_batch_synthetic_canonical_alias_stays_unknown(monkeypatch) -> None:
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))
    monkeypatch.setattr(bridge, "get_event", lambda event_id: bridge._normalize_detail(_BATCH_EVENT))
    assert bridge.get_events(["applescript::Work::start::Planning"]) == {}


@pytest.mark.parametrize("error_code", ["PERMISSION_DENIED", "PERMISSION_UNKNOWN", "APPLESCRIPT_FALLBACK_TIMEOUT", "INVALID_HELPER_OUTPUT"])
def test_batch_native_miss_with_failed_confirmation_is_unknown(monkeypatch, error_code) -> None:
    bridge = _batch_bridge(monkeypatch, {}, {"items": [{"event_id": "a", "found": False, "error_code": "EVENT_NOT_FOUND"}]})

    def fail_confirmation(event_id):
        raise CalendarBridgeError(error_code, "unknown")

    monkeypatch.setattr(bridge, "get_event", fail_confirmation)
    assert bridge.get_events(["a"]) == {}


def test_batch_permission_failure_preserves_existing_single_get_fallback(monkeypatch) -> None:
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))

    def native(command, *args):
        raise CalendarBridgeError("PERMISSION_DENIED", "native permission denied")

    monkeypatch.setattr(bridge, "_run_helper", native)
    monkeypatch.setattr(bridge, "_fallback_get_event", lambda event_id: {**_BATCH_EVENT, "event_id": event_id})

    assert bridge.get_events(["a"])["a"].model_dump() == bridge.get_event("a").model_dump()


def test_batch_transport_failure_remains_explicit(monkeypatch) -> None:
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))

    def native(command, *args):
        raise CalendarBridgeError("HELPER_UNAVAILABLE", "transport failure")

    monkeypatch.setattr(bridge, "_run_helper", native)
    with pytest.raises(CalendarBridgeError) as failure:
        bridge.get_events(["a"])
    assert failure.value.error_code == "HELPER_UNAVAILABLE"


def test_batch_chunks_by_actual_encoded_bytes_and_dedupes_input(monkeypatch) -> None:
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))
    calls = []
    ids = ["first", *["é😀" * 100 + str(index) for index in range(90)]]

    def native(command, *args):
        assert command == "get-calendar-events"
        assert len(args[0].encode("utf-8")) <= bridge._MAX_BATCH_PAYLOAD_BYTES
        requested = json.loads(args[0])["event_ids"]
        calls.append(requested)
        return {"items": [
            {"event_id": event_id, "found": True, "event": {**_BATCH_EVENT, "event_id": event_id}}
            for event_id in requested
        ]}

    monkeypatch.setattr(bridge, "_run_helper", native)
    result = bridge.get_events([*ids, ids[0]])
    assert len(calls) > 1
    assert [event_id for call in calls for event_id in call] == ids
    assert list(result) == ids



def test_batch_canonical_native_id_is_confirmed_with_single_get(monkeypatch) -> None:
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))
    raw = {**_BATCH_EVENT, "event_id": "calendar-item-id"}
    calls = []

    def native(command, *args):
        calls.append((command, args))
        if command == "get-calendar-events":
            return {"items": [{"event_id": "event-identifier", "found": True, "event": raw}]}
        assert command == "get-calendar-event"
        assert args == ("event-identifier",)
        return dict(raw)

    monkeypatch.setattr(bridge, "_run_helper", native)
    expected = bridge.get_event("event-identifier")
    calls.clear()
    result = bridge.get_events(["event-identifier"])
    assert result["event-identifier"].model_dump() == expected.model_dump()
    assert [command for command, args in calls] == ["get-calendar-events", "get-calendar-event"]


@pytest.mark.parametrize("confirmation", ["missing", "permission", "other-id"])
def test_batch_unconfirmed_canonical_alias_stays_unknown(monkeypatch, confirmation) -> None:
    bridge = _batch_bridge(monkeypatch, {}, {"items": [{
        "event_id": "a", "found": True, "event": {**_BATCH_EVENT, "event_id": "canonical"},
    }]})

    def confirm(event_id):
        if confirmation == "missing":
            raise CalendarBridgeError("EVENT_NOT_FOUND", "conflicts with prior found assertion")
        if confirmation == "permission":
            raise CalendarBridgeError("PERMISSION_DENIED", "unknown")
        return bridge._normalize_detail({**_BATCH_EVENT, "event_id": "different"})

    monkeypatch.setattr(bridge, "get_event", confirm)
    assert bridge.get_events(["a"]) == {}


@pytest.mark.parametrize("canonical_id", [None, "", " ", 42])
def test_batch_invalid_canonical_ids_stay_unknown_without_confirmation(monkeypatch, canonical_id) -> None:
    bridge = _batch_bridge(monkeypatch, {}, {"items": [{
        "event_id": "a", "found": True, "event": {**_BATCH_EVENT, "event_id": canonical_id},
    }]})

    def unexpected(event_id):
        raise AssertionError("invalid record must not trigger confirmation")

    monkeypatch.setattr(bridge, "get_event", unexpected)
    assert bridge.get_events(["a"]) == {}


def test_unsupported_legacy_identifier_is_unknown_without_lookup(monkeypatch) -> None:
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))

    def unexpected(*args):
        raise AssertionError("unsupported legacy identity must remain unknown")

    monkeypatch.setattr(bridge, "_run_helper", unexpected)
    assert bridge.get_events(["uid:Work:legacy-id"]) == {}


@pytest.mark.parametrize("error_code", ["PERMISSION_DENIED", "HELPER_COMPILE_FAILED", "HELPER_SOURCE_MISSING"])
def test_batch_unavailable_native_backend_cannot_confirm_opaque_id_absence(monkeypatch, error_code) -> None:
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))

    def native(command, *args):
        raise CalendarBridgeError(error_code, "native backend cannot answer")

    def fallback(event_id):
        raise CalendarBridgeError("EVENT_NOT_FOUND", "opaque native ID is not a JXA UID")

    monkeypatch.setattr(bridge, "_run_helper", native)
    monkeypatch.setattr(bridge, "_fallback_get_event", fallback)
    assert bridge.get_events(["opaque-native-id"]) == {}


def test_legacy_metadata_identifier_cannot_confirm_fallback_miss(monkeypatch) -> None:
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))

    def native(command, *args):
        raise CalendarBridgeError("PERMISSION_DENIED", "native backend cannot answer")

    def fallback(event_id):
        raise CalendarBridgeError("EVENT_NOT_FOUND", "supported synthetic ID definitively missing")

    monkeypatch.setattr(bridge, "_run_helper", native)
    monkeypatch.setattr(bridge, "_fallback_get_event", fallback)
    event_id = "applescript::Work::2026-03-27T10:00:00.000Z::Missing"
    assert bridge.get_events([event_id]) == {}

# Execute generated scripts against deterministic app objects in automatic CI.
# The harness records every write and filtered query; it never opens Calendar.
_JXA_IDENTITY_STUB = """
const fixture = __FIXTURE__;
const writes = [];
const queries = [];
function makeEvent(data) {
  const event = {};
  if (Object.prototype.hasOwnProperty.call(data, "uid")) {
    event.uid = function () { return data.uid; };
  }
  if (Object.prototype.hasOwnProperty.call(data, "id")) {
    event.id = function () { return data.id; };
  }
  ["summary", "startDate", "endDate", "location", "description"].forEach(function(field) {
    const key = {summary: "title", startDate: "start", endDate: "end",
      location: "location", description: "notes"}[field];
    Object.defineProperty(event, field, {
      get: function () { return function () {
        return field === "startDate" || field === "endDate"
          ? new Date(data[key]) : (data[key] || "");
      }; },
      set: function (value) {
        writes.push({id: data.id, uid: data.uid, field: field});
        data[key] = value instanceof Date ? value.toISOString() : value;
      }
    });
  });
  Object.defineProperty(event, "alldayEvent", {
    set: function () { writes.push({id: data.id, field: "alldayEvent"}); }
  });
  event.delete = function () { writes.push({id: data.id, uid: data.uid, field: "delete"}); };
  return event;
}
const calendarObjects = fixture.calendars.map(function(data) {
  const events = data.events.map(makeEvent);
  const calendar = {name: function () { return data.name; }};
  if (Object.prototype.hasOwnProperty.call(data, "id")) {
    calendar.id = function () { return data.id; };
  }
  calendar.events = {
    whose: function (query) {
      return function () {
        queries.push(Object.keys(query));
        if (data.unsupported_id && Object.prototype.hasOwnProperty.call(query, "id")) {
          throw new Error("id property unsupported");
        }
        if (data.unverifiable && Object.prototype.hasOwnProperty.call(query, "id")) {
          return events;
        }
        return events.filter(function(event) {
          if (Object.prototype.hasOwnProperty.call(query, "uid")) {
            return typeof event.uid === "function" && event.uid() === query.uid;
          }
          if (Object.prototype.hasOwnProperty.call(query, "id")) {
            return typeof event.id === "function" && event.id() === query.id;
          }
          if (Object.prototype.hasOwnProperty.call(query, "summary")) {
            return event.summary() === query.summary &&
              event.startDate().getTime() === query.startDate.getTime();
          }
          return event.startDate() > query.startDate._greaterThan &&
            event.startDate() < query.startDate._lessThan;
        });
      };
    },
    push: function () { writes.push({field: "push"}); throw new Error("unexpected push"); }
  };
  return calendar;
});
function Application() {
  const calendars = function () { return calendarObjects; };
  calendars.byName = function (name) {
    return calendarObjects.find(function(cal) { return cal.name() === name; });
  };
  return {calendars: calendars, Event: function () {
    writes.push({field: "create"}); throw new Error("unexpected Event");
  }};
}
"""


def _identity_event(**fields):
    return {
        "title": "Planning", "start": "2026-03-27T10:00:00Z",
        "end": "2026-03-27T10:30:00Z", **fields,
    }


def _jxa_token(**fields):
    payload = {
        "v": 2, "calendar": {"kind": "name", "value": "Work"},
        "calendar_name": "Work", "kind": "id", "value": "left",
        "uid": None, "id": "left", **fields,
    }
    return "applescript::v2::" + quote(json.dumps(payload, separators=(",", ":")), safe="")


def _decode_jxa_token(event_id):
    return json.loads(unquote(event_id.removeprefix("applescript::v2::")))


def _identity_bridge(monkeypatch, tmp_path, calendars):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required to execute generated JXA")
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))
    state = {"writes": [], "queries": [], "native": [], "count": 0}

    def native(command, *args):
        state["native"].append(command)
        if command == "calendar-access-status":
            return {"can_read_events": False}
        if command == "get-calendar-events":
            return {"items": [
                {"event_id": event_id, "found": False, "error_code": "EVENT_NOT_FOUND"}
                for event_id in json.loads(args[0])["event_ids"]
            ]}
        raise CalendarBridgeError("EVENT_NOT_FOUND", "use the generated JXA fallback")

    def jxa(script, *args, timeout=None):
        state["count"] += 1
        path = tmp_path / f"identity-{state['count']}.js"
        stub = _JXA_IDENTITY_STUB.replace("__FIXTURE__", json.dumps({"calendars": calendars}))
        trailer = """
try {
  console.log(JSON.stringify({payload: JSON.parse(run(process.argv.slice(2))),
    writes: writes, queries: queries}));
} catch (error) {
  console.log(JSON.stringify({error: String(error), writes: writes, queries: queries}));
}
"""
        path.write_text(stub + script + trailer)
        completed = subprocess.run([node, str(path), *args], capture_output=True, text=True, check=False)
        assert completed.returncode == 0, completed.stderr
        result = json.loads(completed.stdout)
        state["writes"].extend(result["writes"])
        state["queries"].extend(result["queries"])
        if "error" in result:
            raise CalendarBridgeError("APPLESCRIPT_FALLBACK_FAILED", result["error"])
        return result["payload"]

    monkeypatch.setattr(bridge, "_run_helper", native)
    monkeypatch.setattr(bridge, "_run_jxa", jxa)
    return bridge, state


def _listed_ids(bridge):
    return [
        event.event_id for event in bridge.list_events(
            "2026-03-27T09:00:00+00:00", "2026-03-27T11:00:00+00:00", calendar_id="Work",
        )
    ]


@pytest.mark.parametrize("ids", [("left", "right"), (41, 42)])
@pytest.mark.parametrize("uid_mode", ["absent", "null"])
def test_jxa_no_uid_twins_keep_distinct_strong_ids_and_batch_parity(monkeypatch, tmp_path, ids, uid_mode):
    extra = {"uid": None} if uid_mode == "null" else {}
    bridge, state = _identity_bridge(monkeypatch, tmp_path, [{
        "name": "Work", "id": "calendar-1",
        "events": [_identity_event(id=value, **extra) for value in ids],
    }])
    listed = _listed_ids(bridge)
    assert len(listed) == len(set(listed)) == 2
    assert [_decode_jxa_token(value)["value"] for value in listed] == list(ids)
    for event_id in listed:
        single = bridge.get_event(event_id)
        assert single.event_id == event_id
        assert bridge.get_events([event_id])[event_id].model_dump() == single.model_dump()
    assert "get-calendar-event" not in state["native"]
    assert state["writes"] == []


def test_jxa_uid_tokens_preserve_legacy_uid_and_numeric_id_aliases(monkeypatch, tmp_path):
    bridge, state = _identity_bridge(monkeypatch, tmp_path, [{
        "name": "Work", "events": [_identity_event(uid="legacy-uid", id=41)],
    }])
    emitted = _listed_ids(bridge)[0]
    assert _decode_jxa_token(emitted)["kind"] == "uid"
    for requested in [emitted, "legacy-uid", "41"]:
        single = bridge.get_event(requested)
        assert single.event_id == emitted
        assert bridge.get_events([requested])[requested].model_dump() == single.model_dump()
    assert state["writes"] == []
    assert all(query in [["uid"], ["id"], ["startDate"]] for query in state["queries"])


@pytest.mark.parametrize("identity", [{"uid": None}, {"uid": None, "id": "same"}])
def test_jxa_unstable_or_duplicate_provider_ids_are_display_only(monkeypatch, tmp_path, identity):
    bridge, state = _identity_bridge(monkeypatch, tmp_path, [{
        "name": "Work", "events": [_identity_event(**identity), _identity_event(**identity)],
    }])
    listed = _listed_ids(bridge)
    assert len(listed) == len(set(listed)) == 2
    assert all(_decode_jxa_token(value)["kind"] == "weak" for value in listed)
    assert bridge.get_events(listed) == {}
    for event_id in listed:
        with pytest.raises(CalendarBridgeError):
            bridge.update_event(event_id, title="wrong")
        with pytest.raises(CalendarBridgeError):
            bridge.delete_event(event_id)
    assert state["writes"] == []


@pytest.mark.parametrize("requested", ["left", "same-uid", "applescript::Work::2026-03-27T10:00:00.000Z::Planning"])
def test_jxa_legacy_collisions_refuse_read_batch_and_writes(monkeypatch, tmp_path, requested):
    if requested == "left":
        events = [_identity_event(uid="left", id="one"), _identity_event(uid="other", id="left")]
    elif requested == "same-uid":
        events = [_identity_event(uid="same-uid", id="one"), _identity_event(uid="same-uid", id="two")]
    else:
        events = [_identity_event(id="one"), _identity_event(id="two")]
    bridge, state = _identity_bridge(monkeypatch, tmp_path, [{"name": "Work", "events": events}])
    with pytest.raises(CalendarBridgeError, match="AMBIGUOUS"):
        bridge.get_event(requested)
    assert bridge.get_events([requested]) == {}
    with pytest.raises(CalendarBridgeError):
        bridge.update_event(requested, title="wrong")
    with pytest.raises(CalendarBridgeError):
        bridge.delete_event(requested)
    assert state["writes"] == []


def test_jxa_scoped_tokens_avoid_same_uid_in_another_calendar(monkeypatch, tmp_path):
    bridge, state = _identity_bridge(monkeypatch, tmp_path, [
        {"name": "Work", "id": "work", "events": [_identity_event(uid="same", id="work-event")]},
        {"name": "Personal", "id": "personal", "events": [_identity_event(uid="same", id="personal-event")]},
    ])
    event_id = _listed_ids(bridge)[0]
    assert bridge.get_events([event_id])[event_id].calendar_name == "Work"
    assert bridge.update_event(event_id, title="correct").calendar_name == "Work"
    assert bridge.delete_event(event_id) is True
    assert [write["id"] for write in state["writes"]] == ["work-event", "work-event"]
    assert "update-calendar-event" not in state["native"]
    assert "delete-calendar-event" not in state["native"]
    with pytest.raises(CalendarBridgeError, match="AMBIGUOUS"):
        bridge.get_event("same")


def test_jxa_protocol_looking_legacy_uid_collision_is_not_actionable(monkeypatch, tmp_path):
    token = _jxa_token()
    bridge, state = _identity_bridge(monkeypatch, tmp_path, [{
        "name": "Work", "events": [
            _identity_event(id="left"), _identity_event(uid=token, id="shadow"),
        ],
    }])
    assert bridge.get_events([token]) == {}
    with pytest.raises(CalendarBridgeError, match="AMBIGUOUS"):
        bridge.delete_event(token)
    assert state["writes"] == []


@pytest.mark.parametrize("change", [
    {"calendar": {"kind": "name", "value": "Missing"}},
    {"calendar": {"kind": "name", "value": 41}},
    {"kind": "uid", "value": 41},
    {"kind": "other"},
])
def test_jxa_missing_scope_and_malformed_tokens_are_unknown(monkeypatch, tmp_path, change):
    bridge, state = _identity_bridge(monkeypatch, tmp_path, [{
        "name": "Work", "events": [_identity_event(id="left")],
    }])
    token = _jxa_token(**change)
    assert bridge.get_events([token]) == {}
    with pytest.raises(CalendarBridgeError):
        bridge.update_event(token, title="wrong")
    assert state["writes"] == []


def test_jxa_verified_scoped_miss_is_none_but_unsupported_namespace_is_unknown(monkeypatch, tmp_path):
    bridge, state = _identity_bridge(monkeypatch, tmp_path, [{"name": "Work", "events": []}])
    missing = _jxa_token(value="missing", id="missing")
    assert bridge.get_events([missing]) == {missing: None}
    with pytest.raises(CalendarBridgeError) as error:
        bridge.get_event(missing)
    assert error.value.error_code == "EVENT_NOT_FOUND"
    unsupported, _ = _identity_bridge(monkeypatch, tmp_path, [{
        "name": "Work", "unsupported_id": True, "events": [],
    }])
    assert unsupported.get_events([missing]) == {}
    assert state["writes"] == []


def test_jxa_duplicate_name_scope_is_unknown_and_keeps_both_list_rows(monkeypatch, tmp_path):
    bridge, state = _identity_bridge(monkeypatch, tmp_path, [
        {"name": "Work", "events": [_identity_event(id="left")]},
        {"name": "Work", "events": [_identity_event(id="left")]},
    ])
    listed = _listed_ids(bridge)
    assert len(listed) == len(set(listed)) == 2
    assert bridge.get_events([_jxa_token()]) == {}
    with pytest.raises(CalendarBridgeError):
        bridge.delete_event(_jxa_token())
    assert state["writes"] == []


@pytest.mark.parametrize("calendar", [
    {"name": "Work", "unverifiable": True, "events": [_identity_event(id="right")]},
    {"name": "Work", "events": [_identity_event(id="left"), _identity_event(id="left")]},
])
def test_jxa_filtered_results_are_verified_and_duplicates_rejected(monkeypatch, tmp_path, calendar):
    bridge, state = _identity_bridge(monkeypatch, tmp_path, [calendar])
    token = _jxa_token()
    assert bridge.get_events([token]) == {}
    with pytest.raises(CalendarBridgeError):
        bridge.delete_event(token)
    assert state["writes"] == []


def test_jxa_mutation_refuses_stale_calendar_name_and_clone_move_before_writes(monkeypatch, tmp_path):
    bridge, state = _identity_bridge(monkeypatch, tmp_path, [{
        "name": "Work", "id": "work", "events": [_identity_event(id="left")],
    }])
    emitted = _listed_ids(bridge)[0]
    stale = _decode_jxa_token(emitted)
    stale["calendar_name"] = "Old name"
    token = "applescript::v2::" + quote(json.dumps(stale, separators=(",", ":")), safe="")
    with pytest.raises(CalendarBridgeError, match="STALE_CALENDAR"):
        bridge.update_event(token, title="wrong")
    with pytest.raises(CalendarBridgeError) as move_failure:
        bridge.update_event(emitted, calendar_id="Personal", title="wrong")
    assert move_failure.value.error_code == "UNSUPPORTED_OPERATION"
    assert move_failure.value.suggestion == "Use native Calendar access to move this event."
    assert "retry" not in (move_failure.value.suggestion or "").lower()
    assert state["writes"] == []


def test_jxa_weak_legacy_identifier_cannot_be_used_for_mutation(monkeypatch, tmp_path):
    bridge, state = _identity_bridge(monkeypatch, tmp_path, [{
        "name": "Work", "events": [_identity_event(id="left")],
    }])
    legacy = "applescript::Work::2026-03-27T10:00:00.000Z::Planning"
    assert bridge.get_event(legacy).title == "Planning"
    with pytest.raises(CalendarBridgeError, match="UNSUPPORTED_WEAK"):
        bridge.delete_event(legacy)
    assert state["writes"] == []


def test_jxa_calendar_snapshot_is_bounded_before_filtered_lookup(monkeypatch, tmp_path):
    bridge, state = _identity_bridge(monkeypatch, tmp_path, [
        {"name": "Work", "id": index, "events": []} for index in range(1001)
    ])
    assert bridge.get_events([_jxa_token()]) == {}
    assert state["queries"] == state["writes"] == []


def test_jxa_provider_marker_is_private_and_untrusted_alias_is_not_accepted(monkeypatch):
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))
    token = _jxa_token()
    detail = bridge._normalize_detail(
        {**_BATCH_EVENT, "event_id": token}, identifier_provider="jxa",
    )
    assert detail._identifier_provider == "jxa"
    untrusted = bridge._normalize_detail({**_BATCH_EVENT, "__bridge_provider": "jxa"})
    assert untrusted._identifier_provider is None
    assert "__bridge_provider" not in detail.model_dump()
    assert "_identifier_provider" not in detail.model_dump()
    detail._identifier_provider = None
    monkeypatch.setattr(bridge, "get_event", lambda event_id: detail)
    resolved = {}
    bridge._resolve_batch_individually(["left"], resolved)
    assert resolved == {}


@pytest.mark.parametrize("kind", ["get", "list", "update", "delete"])
def test_generated_calendar_identity_scripts_compile_on_macos(monkeypatch, tmp_path, kind):
    compiler = shutil.which("osacompile")
    if compiler is None:
        pytest.skip("osacompile requires macOS")
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))

    def compile_script(script, *args, timeout=None):
        source = tmp_path / f"{kind}.js"
        source.write_text(script)
        completed = subprocess.run(
            [compiler, "-l", "JavaScript", "-o", str(tmp_path / f"{kind}.scpt"), str(source)],
            capture_output=True, text=True, check=False,
        )
        assert completed.returncode == 0, completed.stderr
        return {"deleted": True, "items": []}

    monkeypatch.setattr(bridge, "_run_jxa", compile_script)
    if kind == "get":
        bridge._fallback_get_event(_jxa_token())
    elif kind == "list":
        bridge._fallback_list_events("2026-03-27T09:00:00Z", "2026-03-27T11:00:00Z", "Work")
    elif kind == "delete":
        bridge._fallback_delete_event(_jxa_token())
    else:
        bridge._fallback_update_event(
            _jxa_token(), title=None, calendar_id=None, start_iso=None, end_iso=None,
            notes=None, location=None, all_day=None,
        )


def test_run_jxa_keeps_recovery_guidance_for_unrelated_process_failures(monkeypatch):
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(
        args, returncode=1, stdout="", stderr="Calendar.app automation failed",
    ))

    with pytest.raises(CalendarBridgeError) as failure:
        bridge._run_jxa("generated script")

    assert failure.value.error_code == "APPLESCRIPT_FALLBACK_FAILED"
    assert failure.value.message == "Calendar.app automation failed"
    assert failure.value.suggestion == "Confirm Calendar.app automation is allowed, then retry."


@pytest.mark.parametrize('argument', ['-e', '-s', '--', '-eJSON.stringify({injected:true})'])
def test_jxa_caller_arguments_never_become_interpreter_options(monkeypatch, argument):
    bridge = CalendarBridge(Path('/tmp/source.swift'), Path('/tmp/helper'))
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs['timeout']))
        return subprocess.CompletedProcess(command, 0, stdout='{}', stderr='')

    monkeypatch.setattr(subprocess, 'run', run)
    bridge._run_jxa('generated script', argument)
    assert calls == [(['osascript', '-l', 'JavaScript', '-e', 'generated script', '--', argument], 30)]


def test_create_event_includes_alarms_in_request(monkeypatch) -> None:
    captured: dict[str, object] = {}
    bridge = _capture_bridge(monkeypatch, captured, {"alarms": [{"type": "relative", "offset_minutes": -15}]})

    event = bridge.create_event(
        title="Planning",
        calendar_id="calendar-1",
        start_iso="2026-03-27T10:00:00-05:00",
        end_iso="2026-03-27T10:30:00-05:00",
        alarms=[{"minutes_before": 15.0}],
    )

    assert captured["command"] == "create-calendar-event"
    assert captured["request"]["alarms"] == [{"minutes_before": 15.0}]
    assert [(a.type, a.offset_minutes) for a in event.alarms] == [("relative", -15)]


def test_create_event_omits_alarms_key_when_none(monkeypatch) -> None:
    captured: dict[str, object] = {}
    bridge = _capture_bridge(monkeypatch, captured)

    bridge.create_event(
        title="Planning",
        calendar_id="calendar-1",
        start_iso="2026-03-27T10:00:00-05:00",
        end_iso="2026-03-27T10:30:00-05:00",
    )

    assert "alarms" not in captured["request"]


def test_update_event_sends_empty_alarms_to_clear(monkeypatch) -> None:
    captured: dict[str, object] = {}
    bridge = _capture_bridge(monkeypatch, captured)

    bridge.update_event("event-123", alarms=[])

    assert captured["command"] == "update-calendar-event"
    assert captured["request"]["alarms"] == []


def test_update_event_omits_alarms_key_when_unchanged(monkeypatch) -> None:
    captured: dict[str, object] = {}
    bridge = _capture_bridge(monkeypatch, captured)

    bridge.update_event("event-123", title="Renamed")

    assert captured["request"] == {"title": "Renamed"}


def test_update_event_sends_absolute_alarms(monkeypatch) -> None:
    captured: dict[str, object] = {}
    bridge = _capture_bridge(monkeypatch, captured, {"alarms": [{"type": "absolute", "absolute": "2026-03-27T09:00:00-05:00"}]})

    event = bridge.update_event("event-123", alarms=[{"absolute_iso": "2026-03-27T09:00:00-05:00"}])

    assert captured["request"]["alarms"] == [{"absolute_iso": "2026-03-27T09:00:00-05:00"}]
    assert [(a.type, a.absolute) for a in event.alarms] == [
        ("absolute", "2026-03-27T09:00:00-05:00")
    ]


def test_get_event_reports_location_alarms(monkeypatch) -> None:
    """Location alarm records retain raw proximity, title, and offset metadata."""
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))

    def fake_run_helper(command: str, *args: str) -> dict[str, object]:
        return {**_EVENT_PAYLOAD, "alarms": [{
            "type": "location",
            "proximity": "leave",
            "location_title": "Office",
            "offset_minutes": 22,
        }]}

    monkeypatch.setattr(bridge, "_run_helper", fake_run_helper)

    alarm = bridge.get_event("event-123").alarms[0]

    assert alarm.type == "location"
    assert alarm.proximity == "leave"
    assert alarm.location_title == "Office"
    assert alarm.offset_minutes == 22


def test_get_event_normalizes_alarms(monkeypatch) -> None:
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))

    def fake_run_helper(command: str, *args: str) -> dict[str, object]:
        assert command == "get-calendar-event"
        return {**_EVENT_PAYLOAD, "alarms": [{"type": "relative", "offset_minutes": -15}, {"type": "absolute", "absolute": "2026-03-27T09:00:00-05:00"}]}

    monkeypatch.setattr(bridge, "_run_helper", fake_run_helper)

    event = bridge.get_event("event-123")

    assert [a.type for a in event.alarms] == ["relative", "absolute"]
    assert event.alarms[0].offset_minutes == -15
    assert event.alarms[1].absolute == "2026-03-27T09:00:00-05:00"



@pytest.mark.parametrize("operation", ["create", "update"])
@pytest.mark.parametrize("alarms", [None, [], [{"minutes_before": 15}]])
@pytest.mark.parametrize("error_code", ["PERMISSION_DENIED", "CALENDAR_NOT_FOUND", "EVENT_NOT_FOUND"])
def test_alarm_mutation_fallback_is_explicit(monkeypatch, operation, alarms, error_code) -> None:
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))
    fallback_calls = []

    def fail_native(command, *args):
        raise CalendarBridgeError(error_code, "native unavailable")

    def fallback(*args, **kwargs):
        fallback_calls.append((args, kwargs))
        return dict(_EVENT_PAYLOAD)

    monkeypatch.setattr(bridge, "_run_helper", fail_native)
    monkeypatch.setattr(bridge, "_fallback_create_event", fallback)
    monkeypatch.setattr(bridge, "_fallback_update_event", fallback)

    def mutate():
        if operation == "create":
            return bridge.create_event(
                title="Planning", calendar_id="calendar-1",
                start_iso=_EVENT_PAYLOAD["start"], end_iso=_EVENT_PAYLOAD["end"], alarms=alarms,
            )
        return bridge.update_event("event-123", title="Planning", alarms=alarms)

    assert mutate().event_id == "event-123"
    assert len(fallback_calls) == 1
    assert fallback_calls[0][1]["alarms"] == alarms


@pytest.mark.parametrize("operation", ["create", "update"])
def test_direct_bridge_rejects_overflowing_alarm_before_helper(monkeypatch, operation) -> None:
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))

    def unexpected(*args):
        raise AssertionError("invalid alarm must be rejected before helper invocation")

    monkeypatch.setattr(bridge, "_run_helper", unexpected)
    with pytest.raises(ValueError):
        if operation == "create":
            bridge.create_event(
                title="Planning", calendar_id="calendar-1",
                start_iso=_EVENT_PAYLOAD["start"], end_iso=_EVENT_PAYLOAD["end"],
                alarms=[{"minutes_before": 10**400}],
            )
        else:
            bridge.update_event("event-123", alarms=[{"minutes_before": 10**400}])

_ALARM_COLLECTION_STUB = r'''
function alarmCollection(values) {
  const collection = function () { return values.slice(); };
  collection.push = function (alarm) {
    alarm.delete = function () { values.splice(values.indexOf(alarm), 1); };
    values.push(alarm);
  };
  values.slice().forEach(function (alarm) { alarm.delete = function () { values.splice(values.indexOf(alarm), 1); }; });
  return collection;
}
function makeAlarm(properties) {
  return {
    triggerDate: function () { return properties.triggerDate || null; },
    triggerInterval: function () { return properties.triggerInterval || 0; }
  };
}
STUB_EVENT.displayAlarms = alarmCollection([makeAlarm({triggerInterval: -15})]);
STUB_EVENT.soundAlarms = alarmCollection([]);
STUB_EVENT.mailAlarms = alarmCollection([]);
STUB_EVENT.openFileAlarms = alarmCollection([]);
const alarmApp = Application();
alarmApp.DisplayAlarm = makeAlarm;
Application = function () { return alarmApp; };
'''


@pytest.mark.parametrize('alarms,expected', [
    (None, [('relative', -15, None)]),
    ([], []),
    ([{'minutes_before': 30}], [('relative', -30, None)]),
    ([{'absolute_iso': '2030-10-11T10:00:00Z'}], [('absolute', None, '2030-10-11T10:00:00.000Z')]),
])
def test_generated_jxa_alarm_update_preserves_replaces_and_clears(monkeypatch, alarms, expected):
    bridge = CalendarBridge(Path('/tmp/source.swift'), Path('/tmp/helper'))

    def run(script, *args, **kwargs):
        return _run_jxa_update_in_node(_ALARM_COLLECTION_STUB + script, args[0], args[1])

    monkeypatch.setattr(bridge, '_run_jxa', run)
    result = bridge._fallback_update_event('event-1', title=None, calendar_id=None, start_iso=None, end_iso=None, notes=None, location=None, all_day=None, alarms=alarms)
    assert [(a['type'], a.get('offset_minutes'), a.get('absolute')) for a in result['alarms']] == expected


def test_native_list_events_preserves_alarm_metadata(monkeypatch):
    bridge = CalendarBridge(Path('/tmp/source.swift'), Path('/tmp/helper'))
    monkeypatch.setattr(bridge, '_helper_read_blocked', lambda: False)
    monkeypatch.setattr(bridge, '_run_helper', lambda *args: {'items': [{**_EVENT_PAYLOAD, 'alarms': [{'type': 'relative', 'offset_minutes': -15}]}]})
    assert bridge.list_events('2030-10-11T00:00:00Z', '2030-10-12T00:00:00Z')[0].alarms[0].offset_minutes == -15

@pytest.mark.parametrize('end,start', [
    ('2026-03-27T13:00:00Z', None),
    (None, 'not-a-date'),
])
@pytest.mark.parametrize('alarms', [[], [{'minutes_before': 30}]])
def test_failed_time_validation_preserves_existing_alarms(monkeypatch, end, start, alarms):
    bridge = CalendarBridge(Path('/tmp/source.swift'), Path('/tmp/helper'))
    observed = []
    def run(script, *args, **kwargs):
        wrapped = script + '''
const updateEvent = run;
run = function(argv) {
  const result = JSON.parse(updateEvent(argv));
  result.originals = eventAlarms(STUB_EVENT);
  return JSON.stringify(result);
};
'''
        result = _run_jxa_update_in_node(_ALARM_COLLECTION_STUB + wrapped, args[0], args[1])
        observed.append(result['originals'])
        return result
    monkeypatch.setattr(bridge, '_run_jxa', run)
    with pytest.raises(CalendarBridgeError) as error:
        bridge._fallback_update_event('event-1', title='Must not change', calendar_id=None, start_iso=start, end_iso=end, notes=None, location=None, all_day=None, alarms=alarms)
    assert error.value.error_code == 'INVALID_INPUT'
    assert observed == [[{'type': 'relative', 'offset_minutes': -15}]]


def test_failed_alarm_push_restores_original_alerts(monkeypatch):
    bridge = CalendarBridge(Path('/tmp/source.swift'), Path('/tmp/helper'))
    observed = []
    def run(script, *args, **kwargs):
        wrapped = script + '''
const updateEvent = run;
const originalPush = STUB_EVENT.displayAlarms.push;
STUB_EVENT.displayAlarms.push = function(alarm) {
  if (alarm.triggerInterval() === -30) { throw new Error("Calendar rejected replacement"); }
  originalPush(alarm);
};
run = function(argv) {
  try { updateEvent(argv); } catch(error) {}
  return JSON.stringify({event: eventRecord(STUB_CALENDAR, STUB_EVENT)});
};
'''
        result = _run_jxa_update_in_node(_ALARM_COLLECTION_STUB + wrapped, args[0], args[1])
        observed.append(result['event']['alarms'])
        return result['event']
    monkeypatch.setattr(bridge, '_run_jxa', run)
    bridge._fallback_update_event('event-1', title=None, calendar_id=None, start_iso=None, end_iso=None, notes=None, location=None, all_day=None, alarms=[{'minutes_before':30}])
    assert observed == [[{'type': 'relative', 'offset_minutes': -15}]]


def test_jxa_constructs_each_alarm_immediately_before_push(monkeypatch):
    bridge = CalendarBridge(Path('/tmp/source.swift'), Path('/tmp/helper'))
    def run(script, *args, **kwargs):
        setup = '''
let pending = false;
const push = STUB_EVENT.displayAlarms.push;
alarmApp.DisplayAlarm = function(properties) {
  if (pending) { throw new Error("Multiple unsaved JXA alarm proxies"); }
  pending = true;
  return makeAlarm(properties);
};
STUB_EVENT.displayAlarms.push = function(alarm) { push(alarm); pending = false; };
'''
        return _run_jxa_update_in_node(_ALARM_COLLECTION_STUB + setup + script, args[0], args[1])
    monkeypatch.setattr(bridge, '_run_jxa', run)
    result = bridge._fallback_update_event('event-1', title=None, calendar_id=None, start_iso=None, end_iso=None, notes=None, location=None, all_day=None, alarms=[{'minutes_before':15}, {'minutes_before':30}])
    assert [a['offset_minutes'] for a in result['alarms']] == [-15, -30]


def test_failed_alarm_push_restores_absolute_sound_and_mail_alerts_in_mock(monkeypatch):
    bridge = CalendarBridge(Path('/tmp/source.swift'), Path('/tmp/helper'))
    observed = []
    def run(script, *args, **kwargs):
        setup = '''
function soundAlarm(properties) {
  const alarm = makeAlarm(properties);
  alarm.soundName = function() { return properties.soundName; };
  alarm.soundFile = function() { return properties.soundFile; };
  return alarm;
}
alarmApp.SoundAlarm = soundAlarm;
alarmApp.MailAlarm = makeAlarm;
STUB_EVENT.displayAlarms = alarmCollection([makeAlarm({triggerDate:new Date("2030-10-11T10:00:00Z")})]);
STUB_EVENT.soundAlarms = alarmCollection([soundAlarm({triggerInterval:-20,soundName:"Fixture",soundFile:"/tmp/fixture.aiff"})]);
STUB_EVENT.mailAlarms = alarmCollection([makeAlarm({triggerDate:new Date("2030-10-11T09:00:00Z")})]);
const push = STUB_EVENT.displayAlarms.push;
STUB_EVENT.displayAlarms.push = function(alarm) {
  if (alarm.triggerInterval() === -30) { throw new Error("Rejected"); }
  push(alarm);
};
'''
        wrapped = script + '''
const update = run;
run = function(argv) {
  try { update(argv); } catch(error) {}
  return JSON.stringify({event:eventRecord(STUB_CALENDAR,STUB_EVENT),sound:STUB_EVENT.soundAlarms().map(a=>({name:a.soundName(),file:a.soundFile(),offset:a.triggerInterval()})),mailCount:STUB_EVENT.mailAlarms().length});
};
'''
        result = _run_jxa_update_in_node(_ALARM_COLLECTION_STUB + setup + wrapped, args[0], args[1])
        observed.append(result)
        return result['event']
    monkeypatch.setattr(bridge, '_run_jxa', run)
    bridge._fallback_update_event('event-1', title=None, calendar_id=None, start_iso=None, end_iso=None, notes=None, location=None, all_day=None, alarms=[{'minutes_before':30}])
    result = observed[0]
    assert result['sound'] == [{'name':'Fixture','file':'/tmp/fixture.aiff','offset':-20}]
    assert result['mailCount'] == 1
    assert sorted(a.get('absolute', '') for a in result['event']['alarms'] if a['type']=='absolute') == ['2030-10-11T09:00:00.000Z', '2030-10-11T10:00:00.000Z']


def test_alarm_clear_deletes_positional_jxa_specifiers_in_reverse_order(monkeypatch):
    bridge = CalendarBridge(Path('/tmp/source.swift'), Path('/tmp/helper'))
    def run(script, *args, **kwargs):
        setup = """
const values = [makeAlarm({triggerInterval:-15}),makeAlarm({triggerInterval:-30})];
STUB_EVENT.displayAlarms = function() {
  return values.map(function(value,index) {
    return {triggerDate:value.triggerDate, triggerInterval:value.triggerInterval,
      delete:function() {
        if (index >= values.length) { throw new Error("Positional specifier no longer exists"); }
        values.splice(index,1);
      }};
  });
};
STUB_EVENT.displayAlarms.push = function(alarm) { values.push(alarm); };
"""
        return _run_jxa_update_in_node(_ALARM_COLLECTION_STUB + setup + script, args[0], args[1])
    monkeypatch.setattr(bridge, '_run_jxa', run)
    result = bridge._fallback_update_event('event-1', title=None, calendar_id=None, start_iso=None, end_iso=None, notes=None, location=None, all_day=None, alarms=[])
    assert result['alarms'] == []


@pytest.mark.parametrize("target_present", [True, False])
@pytest.mark.parametrize("shadow_calendar", ["Work", "Personal"])
def test_encoded_legacy_shadow_in_any_calendar_is_unknown_and_blocks_writes(monkeypatch, tmp_path, target_present, shadow_calendar):
    token = _jxa_token()
    work = [_identity_event(id="left")] if target_present else []
    personal = []
    (work if shadow_calendar == "Work" else personal).append(_identity_event(uid=token, id="shadow"))
    bridge, state = _identity_bridge(monkeypatch, tmp_path, [{"name":"Work","events":work},{"name":"Personal","events":personal}])
    assert bridge.get_events([token]) == {}
    for operation in (lambda: bridge.get_event(token), lambda: bridge.update_event(token, title="wrong"), lambda: bridge.delete_event(token)):
        with pytest.raises(CalendarBridgeError, match="AMBIGUOUS"):
            operation()
    assert state["writes"] == []
