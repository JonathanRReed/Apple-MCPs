import pytest

from apple_calendar_mcp import tools
from apple_calendar_mcp.config import load_settings
from apple_calendar_mcp.models import AttendeeInfo, EventDetail, RecurrenceInfo
from apple_calendar_mcp.permissions import SafetyError


class FakeBridge:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def helper_available(self):
        return True, True

    def list_calendars(self):
        return []

    def calendar_access_status(self):
        return {
            "status": "authorized",
            "can_read_events": True,
            "can_write_events": True,
        }

    def list_events(self, start_iso: str, end_iso: str, calendar_id: str | None = None, limit: int = 100):
        return []

    def get_event(self, event_id: str) -> EventDetail:
        return EventDetail(
            event_id=event_id,
            title="Planning",
            calendar_id="calendar-1",
            calendar_name="Work",
            start="2026-03-27T10:00:00-05:00",
            end="2026-03-27T10:30:00-05:00",
            all_day=False,
            location="Room 1",
            availability=None,
            notes="Bring notes",
            recurrence_rule=RecurrenceInfo(frequency="weekly", interval=1, end_date=None),
            attendees=[AttendeeInfo(name="Alex", email="alex@example.com", status="accepted")],
        )

    def create_event(self, title: str, calendar_id: str, start_iso: str, end_iso: str, notes=None, location=None, all_day=False, recurrence=None, alarms=None) -> EventDetail:
        self.calls.append({"method": "create_event", "alarms": alarms})
        return EventDetail(
            event_id="event-new",
            title=title,
            calendar_id=calendar_id,
            calendar_name="Work",
            start="2026-03-27T10:00:00-05:00",
            end="2026-03-27T10:30:00-05:00",
            all_day=all_day,
            location=location,
            availability=None,
            notes=notes,
            alarms=[{"type": "relative", "offset_minutes": -15}] if alarms else None,
        )

    def update_event(
        self,
        event_id: str,
        *,
        title: str | None = None,
        calendar_id: str | None = None,
        start_iso: str | None = None,
        end_iso: str | None = None,
        notes: str | None = None,
        location: str | None = None,
        all_day: bool | None = None,
        recurrence=None,
        alarms=None,
    ) -> EventDetail:
        self.calls.append({"method": "update_event", "title": title, "alarms": alarms})
        return EventDetail(
            event_id=event_id,
            title=title or "Planning",
            calendar_id=calendar_id or "calendar-1",
            calendar_name="Work",
            start="2026-03-27T10:00:00-05:00",
            end="2026-03-27T10:30:00-05:00",
            all_day=bool(all_day),
            location=location,
            availability=None,
            notes=notes,
            alarms=[{"type": "relative", "offset_minutes": -15}] if alarms else None,
        )


def test_calendar_list_events_rejects_invalid_range(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_CALENDAR_MCP_SAFETY_MODE", "safe_manage")
    load_settings.cache_clear()
    monkeypatch.setattr(tools, "_bridge", lambda: FakeBridge())

    result = tools.calendar_list_events("2026-03-27T10:00:00-05:00", "2026-03-27T09:00:00-05:00")

    assert result.ok is False
    assert result.error.error_code == "INVALID_INPUT"


def test_calendar_create_event_returns_structured_event(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_CALENDAR_MCP_SAFETY_MODE", "safe_manage")
    load_settings.cache_clear()
    monkeypatch.setattr(tools, "_bridge", lambda: FakeBridge())

    result = tools.calendar_create_event(
        title="Planning",
        start_iso="2026-03-27T10:00:00-05:00",
        end_iso="2026-03-27T10:30:00-05:00",
        calendar_id="calendar-1",
        notes="Bring notes",
        location="Room 1",
    )

    assert result.ok is True
    assert result.event.event_id == "event-new"


def test_calendar_health_surfaces_permission_state(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_CALENDAR_MCP_SAFETY_MODE", "safe_manage")
    load_settings.cache_clear()
    monkeypatch.setattr(tools, "_bridge", lambda: FakeBridge())

    result = tools.calendar_health()

    assert result.access_status == "authorized"
    assert result.can_read_events is True


def test_calendar_get_event_checks_permissions_before_bridge(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_CALENDAR_MCP_SAFETY_MODE", "safe_manage")
    load_settings.cache_clear()

    class GuardBridge(FakeBridge):
        def get_event(self, event_id: str) -> EventDetail:
            raise AssertionError("bridge should not be called before permissions are enforced")

    def fake_ensure_action_allowed(action: str, calendar_name: str | None = None) -> None:
        raise SafetyError("SAFETY_POLICY_BLOCK", f"{action}:{calendar_name}", "blocked")

    monkeypatch.setattr(tools, "_bridge", lambda: GuardBridge())
    monkeypatch.setattr(tools, "_event_owner_calendar", lambda event_id: "Blocked")
    monkeypatch.setattr(tools, "ensure_action_allowed", fake_ensure_action_allowed)

    result = tools.calendar_get_event("event-1")

    assert result.ok is False
    assert result.error.error_code == "SAFETY_POLICY_BLOCK"


def test_calendar_main_exists() -> None:
    assert callable(tools.main)


def test_calendar_list_events_accepts_string_limit(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_CALENDAR_MCP_SAFETY_MODE", "safe_manage")
    load_settings.cache_clear()
    monkeypatch.setattr(tools, "_bridge", lambda: FakeBridge())

    result = tools.calendar_list_events("2026-03-27T10:00:00-05:00", "2026-03-27T11:00:00-05:00", limit="5")

    assert result.ok is True


def test_calendar_get_event_exposes_attendees_and_recurrence(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_CALENDAR_MCP_SAFETY_MODE", "safe_manage")
    load_settings.cache_clear()
    monkeypatch.setattr(tools, "_bridge", lambda: FakeBridge())

    result = tools.calendar_get_event("event-1")

    assert result.ok is True
    assert result.event.recurrence_rule is not None
    assert result.event.recurrence_rule.frequency == "weekly"
    assert result.event.attendees is not None
    assert result.event.attendees[0].status == "accepted"


def test_calendar_health_reports_applescript_fallback(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_CALENDAR_MCP_SAFETY_MODE", "safe_manage")
    load_settings.cache_clear()

    class FallbackBridge(FakeBridge):
        def calendar_access_status(self):
            return {
                "status": "not_determined",
                "can_read_events": False,
                "can_write_events": False,
                "message": "Calendar access has not been granted yet.",
                "suggestion": "Run a Calendar tool and approve the macOS permission prompt.",
            }

        def list_calendars(self):
            return []

    monkeypatch.setattr(tools, "_bridge", lambda: FallbackBridge())

    result = tools.calendar_health()

    assert result.access_status == "applescript_fallback"
    assert result.can_read_events is True
    assert result.permission_error is None


def test_validate_alarms_returns_none_when_omitted() -> None:
    assert tools._validate_alarms(None) is None


def test_validate_alarms_returns_empty_list_for_clear() -> None:
    assert tools._validate_alarms([]) == []


def test_validate_alarms_normalizes_relative_and_absolute_entries() -> None:
    normalized = tools._validate_alarms(
        [
            {"minutes_before": 15},
            {"absolute_iso": "2026-03-27T09:00:00-05:00"},
        ]
    )

    assert normalized == [
        {"minutes_before": 15.0},
        {"absolute_iso": "2026-03-27T09:00:00-05:00"},
    ]


def test_validate_alarms_accepts_zero_minutes() -> None:
    assert tools._validate_alarms([{"minutes_before": 0}]) == [{"minutes_before": 0.0}]


def test_validate_alarms_accepts_string_minutes() -> None:
    assert tools._validate_alarms([{"minutes_before": "30"}]) == [{"minutes_before": 30.0}]


def test_validate_alarms_rejects_both_fields() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        tools._validate_alarms([{"minutes_before": 15, "absolute_iso": "2026-03-27T09:00:00"}])


def test_validate_alarms_rejects_neither_field() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        tools._validate_alarms([{"note": "ring loudly"}])


def test_validate_alarms_rejects_negative_minutes() -> None:
    with pytest.raises(ValueError, match="zero or greater"):
        tools._validate_alarms([{"minutes_before": -5}])


def test_validate_alarms_rejects_non_numeric_minutes() -> None:
    with pytest.raises(ValueError, match="must be a number"):
        tools._validate_alarms([{"minutes_before": "soon"}])


@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan"), "inf", "nan", "1e400"])
def test_validate_alarms_rejects_non_finite_minutes(value) -> None:
    with pytest.raises(ValueError, match="must be a number"):
        tools._validate_alarms([{"minutes_before": value}])


def test_validate_alarms_rejects_boolean_minutes() -> None:
    with pytest.raises(ValueError, match="must be a number"):
        tools._validate_alarms([{"minutes_before": True}])


def test_validate_alarms_rejects_non_numeric_type_minutes() -> None:
    with pytest.raises(ValueError, match="must be a number"):
        tools._validate_alarms([{"minutes_before": [15]}])


def test_validate_alarms_rejects_fractional_minutes() -> None:
    with pytest.raises(ValueError, match="whole number"):
        tools._validate_alarms([{"minutes_before": 0.5}])


def test_validate_alarms_accepts_whole_float_minutes() -> None:
    assert tools._validate_alarms([{"minutes_before": 15.0}]) == [{"minutes_before": 15.0}]


def test_validate_alarms_rejects_bad_absolute_iso() -> None:
    with pytest.raises(ValueError):
        tools._validate_alarms([{"absolute_iso": "not-a-datetime"}])


def test_validate_alarms_rejects_non_object_entry() -> None:
    with pytest.raises(ValueError, match="must be an object"):
        tools._validate_alarms(["15m"])


def test_calendar_create_event_passes_alarms_to_bridge(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_CALENDAR_MCP_SAFETY_MODE", "safe_manage")
    load_settings.cache_clear()
    bridge = FakeBridge()
    monkeypatch.setattr(tools, "_bridge", lambda: bridge)

    result = tools.calendar_create_event(
        title="Planning",
        start_iso="2026-03-27T10:00:00-05:00",
        end_iso="2026-03-27T10:30:00-05:00",
        calendar_id="calendar-1",
        alarms=[{"minutes_before": 15}],
    )

    assert result.ok is True
    assert [(a.type, a.offset_minutes) for a in result.event.alarms] == [("relative", -15)]
    assert bridge.calls[-1] == {"method": "create_event", "alarms": [{"minutes_before": 15.0}]}


def test_calendar_create_event_omits_alarms_when_not_given(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_CALENDAR_MCP_SAFETY_MODE", "safe_manage")
    load_settings.cache_clear()
    bridge = FakeBridge()
    monkeypatch.setattr(tools, "_bridge", lambda: bridge)

    result = tools.calendar_create_event(
        title="Planning",
        start_iso="2026-03-27T10:00:00-05:00",
        end_iso="2026-03-27T10:30:00-05:00",
        calendar_id="calendar-1",
    )

    assert result.ok is True
    assert bridge.calls[-1]["alarms"] is None


def test_calendar_create_event_rejects_malformed_alarms(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_CALENDAR_MCP_SAFETY_MODE", "safe_manage")
    load_settings.cache_clear()
    bridge = FakeBridge()
    monkeypatch.setattr(tools, "_bridge", lambda: bridge)

    result = tools.calendar_create_event(
        title="Planning",
        start_iso="2026-03-27T10:00:00-05:00",
        end_iso="2026-03-27T10:30:00-05:00",
        calendar_id="calendar-1",
        alarms=[{"minutes_before": -1}],
    )

    assert result.ok is False
    assert result.error.error_code == "INVALID_INPUT"
    assert not any(call["method"] == "create_event" for call in bridge.calls)


def test_calendar_update_event_clears_alarms_with_empty_list(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_CALENDAR_MCP_SAFETY_MODE", "safe_manage")
    load_settings.cache_clear()
    bridge = FakeBridge()
    monkeypatch.setattr(tools, "_bridge", lambda: bridge)
    monkeypatch.setattr(tools, "_event_owner_calendar", lambda event_id: "Work")

    result = tools.calendar_update_event("event-1", alarms=[])

    assert result.ok is True
    assert bridge.calls[-1]["alarms"] == []


def test_calendar_update_event_leaves_alarms_untouched_when_omitted(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_CALENDAR_MCP_SAFETY_MODE", "safe_manage")
    load_settings.cache_clear()
    bridge = FakeBridge()
    monkeypatch.setattr(tools, "_bridge", lambda: bridge)
    monkeypatch.setattr(tools, "_event_owner_calendar", lambda event_id: "Work")

    result = tools.calendar_update_event("event-1", title="Renamed")

    assert result.ok is True
    assert bridge.calls[-1]["alarms"] is None


def test_calendar_update_event_rejects_malformed_alarms(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_CALENDAR_MCP_SAFETY_MODE", "safe_manage")
    load_settings.cache_clear()
    bridge = FakeBridge()
    monkeypatch.setattr(tools, "_bridge", lambda: bridge)
    monkeypatch.setattr(tools, "_event_owner_calendar", lambda event_id: "Work")

    result = tools.calendar_update_event("event-1", alarms=[{"minutes_before": -1}])

    assert result.ok is False
    assert result.error.error_code == "INVALID_INPUT"
    assert not any(call["method"] == "update_event" for call in bridge.calls)


def test_calendar_health_reports_event_alarms_capability(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_CALENDAR_MCP_SAFETY_MODE", "safe_manage")
    load_settings.cache_clear()
    monkeypatch.setattr(tools, "_bridge", lambda: FakeBridge())

    result = tools.calendar_health()

    assert "event_alarms" in result.capabilities


def teardown_function() -> None:
    load_settings.cache_clear()
