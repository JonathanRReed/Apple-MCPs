import json

import pytest

from apple_calendar_mcp import tools
from apple_calendar_mcp.config import load_settings
from apple_calendar_mcp.models import CalendarInfo, EventDetail
from apple_calendar_mcp.permissions import SafetyError, ensure_action_allowed

START = "2026-09-25T00:00:00+00:00"
END = "2026-09-26T00:00:00+00:00"


def event(calendar_id, name, start="2026-09-25T10:00:00+00:00"):
    return EventDetail(
        event_id=f"{calendar_id}-event", title=f"{name} appointment",
        calendar_id=calendar_id, calendar_name=name, start=start,
        end="2026-09-25T20:00:00+00:00", all_day=False,
    )


class ScopeBridge:
    def __init__(self):
        self.calendars = [CalendarInfo(calendar_id="private", name="Private"), CalendarInfo(calendar_id="work", name="Work")]
        self.events = [event("private", "Private"), event("work", "Work")]
        self.queries = []
        self.get_calls = 0
        self.leak_on_scoped_query = False

    def list_calendars(self):
        return self.calendars

    def list_events(self, start_iso, end_iso, calendar_id=None, limit=100):
        self.queries.append(calendar_id)
        items = self.events if calendar_id is None or self.leak_on_scoped_query else [item for item in self.events if item.calendar_id == calendar_id]
        return items[:limit]

    def get_event(self, event_id):
        self.get_calls += 1
        # A second read simulates an event moved between authorization and response.
        return self.events[1] if self.get_calls == 1 else self.events[0]


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch):
    for name in ("APPLE_CALENDAR_MCP_ALLOWED_CALENDARS", "APPLE_CALENDAR_MCP_WRITE_ALLOWED_CALENDARS", "APPLE_CALENDAR_MCP_SAFETY_MODE"):
        monkeypatch.delenv(name, raising=False)
    load_settings.cache_clear()
    yield
    load_settings.cache_clear()


@pytest.fixture
def scoped(monkeypatch):
    monkeypatch.setenv("APPLE_CALENDAR_MCP_ALLOWED_CALENDARS", "Work")
    load_settings.cache_clear()
    bridge = ScopeBridge()
    monkeypatch.setattr(tools, "_bridge", lambda: bridge)
    return bridge


def test_calendar_list_filters_excluded_names(scoped):
    result = tools.calendar_list_calendars()
    assert result.ok is True
    assert [item.name for item in result.calendars] == ["Work"]
    assert result.count == 1


def test_calendar_resource_filters_excluded_names(scoped):
    result = json.loads(tools.calendar_calendars_resource())
    assert [item["name"] for item in result["calendars"]] == ["Work"]
    assert result["count"] == 1
    assert "Private" not in json.dumps(result)


def test_global_event_list_applies_scope_before_limit(scoped):
    result = tools.calendar_list_events(START, END, limit=1)
    assert result.ok is True
    assert [item.calendar_name for item in result.events] == ["Work"]
    assert result.count == 1
    assert scoped.queries == ["work"]


def test_today_resource_uses_the_same_scope(scoped):
    result = json.loads(tools.calendar_events_today_resource())
    assert [item["calendar_name"] for item in result["events"]] == ["Work"]
    assert result["count"] == 1
    assert scoped.queries == ["work"]


def test_explicit_excluded_calendar_is_blocked_without_event_lookup(scoped):
    result = tools.calendar_list_events(START, END, calendar_id="private")
    assert result.ok is False
    assert result.error.error_code == "CALENDAR_BLOCKED"
    assert scoped.queries == []


def test_unknown_explicit_calendar_fails_closed_with_scope(scoped):
    result = tools.calendar_list_events(START, END, calendar_id="unknown")
    assert result.ok is False
    assert result.error.error_code == "CALENDAR_BLOCKED"
    assert scoped.queries == []


def test_no_matching_calendars_does_not_fall_back_to_unrestricted_read(scoped):
    scoped.calendars = [CalendarInfo(calendar_id="private", name="Private")]
    result = tools.calendar_list_events(START, END)
    assert result.ok is True
    assert result.events == []
    assert result.count == 0
    assert scoped.queries == []


def test_scoped_response_filters_unexpected_excluded_events(scoped):
    scoped.leak_on_scoped_query = True
    result = tools.calendar_list_events(START, END)
    assert result.ok is True
    assert [item.calendar_name for item in result.events] == ["Work"]
    assert result.count == 1


def test_get_returns_the_same_event_that_was_authorized(scoped):
    result = tools.calendar_get_event("work-event")
    assert result.ok is True
    assert result.event.calendar_name == "Work"
    assert scoped.get_calls == 1


def test_get_of_excluded_event_is_blocked(scoped):
    scoped.events = [event("work", "Work"), event("private", "Private")]
    result = tools.calendar_get_event("private-event")
    assert result.ok is False
    assert result.error.error_code == "CALENDAR_BLOCKED"
    assert not hasattr(result, "event")


def test_unrestricted_default_preserves_global_reads(monkeypatch):
    bridge = ScopeBridge()
    monkeypatch.setattr(tools, "_bridge", lambda: bridge)
    result = tools.calendar_list_events(START, END)
    assert result.ok is True
    assert {item.calendar_name for item in result.events} == {"Private", "Work"}
    assert bridge.queries == [None]


def test_write_only_scope_does_not_hide_readable_calendars(monkeypatch):
    monkeypatch.setenv("APPLE_CALENDAR_MCP_WRITE_ALLOWED_CALENDARS", "Work")
    load_settings.cache_clear()
    bridge = ScopeBridge()
    monkeypatch.setattr(tools, "_bridge", lambda: bridge)
    assert len(tools.calendar_list_calendars().calendars) == 2
    assert len(tools.calendar_list_events(START, END).events) == 2
    assert len(json.loads(tools.calendar_calendars_resource())["calendars"]) == 2
    assert len(json.loads(tools.calendar_events_today_resource())["events"]) == 2


@pytest.mark.parametrize("action", ["calendar_create_event", "calendar_update_event", "calendar_delete_event"])
def test_read_allowlist_also_blocks_unresolved_write_targets(scoped, action):
    with pytest.raises(SafetyError) as error:
        ensure_action_allowed(action, None)
    assert error.value.error_code == "CALENDAR_BLOCKED"


def test_read_and_write_scopes_compose(monkeypatch):
    monkeypatch.setenv("APPLE_CALENDAR_MCP_ALLOWED_CALENDARS", "Work")
    monkeypatch.setenv("APPLE_CALENDAR_MCP_WRITE_ALLOWED_CALENDARS", "Private")
    load_settings.cache_clear()
    for name in ("Work", "Private"):
        with pytest.raises(SafetyError):
            ensure_action_allowed("calendar_create_event", name)
    ensure_action_allowed("calendar_get_event", "Work")


def test_readonly_mode_overrides_write_allowlist(monkeypatch):
    monkeypatch.setenv("APPLE_CALENDAR_MCP_SAFETY_MODE", "safe_readonly")
    monkeypatch.setenv("APPLE_CALENDAR_MCP_WRITE_ALLOWED_CALENDARS", "Work")
    load_settings.cache_clear()
    with pytest.raises(SafetyError) as error:
        ensure_action_allowed("calendar_create_event", "Work")
    assert error.value.error_code == "WRITE_BLOCKED"


def test_scoped_events_are_globally_sorted_and_limited(monkeypatch, scoped):
    monkeypatch.setenv("APPLE_CALENDAR_MCP_ALLOWED_CALENDARS", "Work,Personal")
    load_settings.cache_clear()
    scoped.calendars.append(CalendarInfo(calendar_id="personal", name="Personal"))
    scoped.events.append(event("personal", "Personal", "2026-09-25T10:30:00+02:00"))
    result = tools.calendar_list_events(START, END, limit=1)
    assert result.ok is True
    assert [item.calendar_name for item in result.events] == ["Personal"]
    assert scoped.queries == ["work", "personal"]


def test_permission_error_is_not_reported_as_empty_success(monkeypatch, scoped):
    def blocked(*args, **kwargs):
        raise tools.CalendarBridgeError("PERMISSION_DENIED", "Calendar permission is unavailable.")
    monkeypatch.setattr(scoped, "list_events", blocked)
    result = tools.calendar_list_events(START, END)
    assert result.ok is False
    assert result.error.error_code == "PERMISSION_DENIED"
