from apple_calendar_mcp.config import load_settings
from apple_calendar_mcp.permissions import SafetyError, ensure_action_allowed


def test_safe_readonly_blocks_create(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_CALENDAR_MCP_SAFETY_MODE", "safe_readonly")
    load_settings.cache_clear()

    try:
        ensure_action_allowed("calendar_create_event", "Personal")
    except SafetyError as exc:
        assert exc.error_code == "WRITE_BLOCKED"
    else:
        raise AssertionError("Expected SafetyError")


def test_allowed_calendar_list_blocks_unlisted_calendar(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_CALENDAR_MCP_SAFETY_MODE", "safe_manage")
    monkeypatch.setenv("APPLE_CALENDAR_MCP_ALLOWED_CALENDARS", "Work,Personal")
    load_settings.cache_clear()

    try:
        ensure_action_allowed("calendar_list_events", "School")
    except SafetyError as exc:
        assert exc.error_code == "CALENDAR_BLOCKED"
    else:
        raise AssertionError("Expected SafetyError")


def teardown_function() -> None:
    load_settings.cache_clear()
