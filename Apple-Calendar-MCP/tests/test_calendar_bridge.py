import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

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


_JXA_NO_UID_STUB = """
const EVENT = {
  uid: function () { return null; },
  id: function () { return "alternate-id"; },
  summary: function () { return "Planning"; },
  startDate: function () { return new Date("2026-03-27T10:00:00Z"); },
  endDate: function () { return new Date("2026-03-27T10:30:00Z"); },
  location: function () { return ""; },
  description: function () { return ""; }
};
const CALENDAR = {
  name: function () { return "Work"; },
  events: {
    whose: function (query) {
      return function () {
        if (Object.prototype.hasOwnProperty.call(query, "uid")) { return []; }
        if (query.summary !== undefined) {
          return query.summary === EVENT.summary() &&
            query.startDate.getTime() === EVENT.startDate().getTime() ? [EVENT] : [];
        }
        return EVENT.startDate() > query.startDate._greaterThan &&
          EVENT.startDate() < query.startDate._lessThan ? [EVENT] : [];
      };
    }
  }
};
function Application() {
  const calendars = function () { return [CALENDAR]; };
  calendars.byName = function (name) { return name === "Work" ? CALENDAR : null; };
  return {calendars: calendars};
}
"""


@pytest.mark.parametrize("has_uid_method", [True, False])
def test_generated_jxa_record_preserves_no_uid_synthetic_identity(monkeypatch, tmp_path, has_uid_method) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required to execute generated JXA")
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))
    script_count = 0

    def native(command, *args):
        if command == "calendar-access-status":
            return {"can_read_events": False}
        raise CalendarBridgeError("PERMISSION_DENIED", "force the real generated fallback")

    def jxa(script, *args, timeout=None):
        nonlocal script_count
        script_count += 1
        path = tmp_path / f"no-uid-{script_count}.js"
        stub = _JXA_NO_UID_STUB if has_uid_method else _JXA_NO_UID_STUB.replace("  uid: function () { return null; },\n", "")
        path.write_text(stub + script + "\nconsole.log(run(process.argv.slice(2)));\n")
        completed = subprocess.run(
            [node, str(path), *args], capture_output=True, text=True, check=False,
        )
        assert completed.returncode == 0, completed.stderr
        return json.loads(completed.stdout.strip())

    monkeypatch.setattr(bridge, "_run_helper", native)
    monkeypatch.setattr(bridge, "_run_jxa", jxa)

    listed = bridge.list_events(
        "2026-03-27T09:00:00+00:00", "2026-03-27T11:00:00+00:00", calendar_id="Work",
    )
    event_id = listed[0].event_id
    assert event_id == "applescript::Work::2026-03-27T10:00:00.000Z::Planning"
    single = bridge.get_event(event_id)
    assert single.event_id == event_id
    assert bridge.get_events([event_id])[event_id].model_dump() == single.model_dump()


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


def test_supported_synthetic_identifier_can_confirm_fallback_miss(monkeypatch) -> None:
    bridge = CalendarBridge(Path("/tmp/source.swift"), Path("/tmp/helper"))

    def native(command, *args):
        raise CalendarBridgeError("PERMISSION_DENIED", "native backend cannot answer")

    def fallback(event_id):
        raise CalendarBridgeError("EVENT_NOT_FOUND", "supported synthetic ID definitively missing")

    monkeypatch.setattr(bridge, "_run_helper", native)
    monkeypatch.setattr(bridge, "_fallback_get_event", fallback)
    event_id = "applescript::Work::2026-03-27T10:00:00.000Z::Missing"
    assert bridge.get_events([event_id]) == {event_id: None}
