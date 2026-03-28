from apple_calendar_mcp.config import load_settings
from apple_calendar_mcp.models import EventDetail
from apple_calendar_mcp import tools
from apple_calendar_mcp.permissions import SafetyError


class FakeBridge:
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
        )

    def create_event(self, title: str, calendar_id: str, start_iso: str, end_iso: str, notes=None, location=None, all_day=False) -> EventDetail:
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


def teardown_function() -> None:
    load_settings.cache_clear()
