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


def _write_only_env(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_CALENDAR_MCP_SAFETY_MODE", "safe_manage")
    monkeypatch.delenv("APPLE_CALENDAR_MCP_ALLOWED_CALENDARS", raising=False)
    monkeypatch.setenv("APPLE_CALENDAR_MCP_WRITE_ALLOWED_CALENDARS", "STUDY")
    load_settings.cache_clear()


def test_write_allowlist_permits_reads_of_other_calendars(monkeypatch) -> None:
    _write_only_env(monkeypatch)

    ensure_action_allowed("calendar_list_events", "Commitments")
    ensure_action_allowed("calendar_get_event", "Family")


def test_write_allowlist_blocks_writes_to_other_calendars(monkeypatch) -> None:
    _write_only_env(monkeypatch)

    for action in ("calendar_create_event", "calendar_update_event", "calendar_delete_event"):
        try:
            ensure_action_allowed(action, "Commitments")
        except SafetyError as exc:
            assert exc.error_code == "CALENDAR_WRITE_BLOCKED"
        else:
            raise AssertionError(f"Expected SafetyError for {action}")


def test_write_allowlist_permits_writes_to_listed_calendar(monkeypatch) -> None:
    _write_only_env(monkeypatch)

    ensure_action_allowed("calendar_create_event", "STUDY")
    ensure_action_allowed("calendar_delete_event", "STUDY")


def test_write_allowlist_fails_closed_on_unresolvable_calendar(monkeypatch) -> None:
    _write_only_env(monkeypatch)

    try:
        ensure_action_allowed("calendar_create_event", None)
    except SafetyError as exc:
        assert exc.error_code == "CALENDAR_WRITE_BLOCKED"
    else:
        raise AssertionError("Expected SafetyError")


def test_no_write_allowlist_leaves_writes_unrestricted(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_CALENDAR_MCP_SAFETY_MODE", "safe_manage")
    monkeypatch.delenv("APPLE_CALENDAR_MCP_ALLOWED_CALENDARS", raising=False)
    monkeypatch.delenv("APPLE_CALENDAR_MCP_WRITE_ALLOWED_CALENDARS", raising=False)
    load_settings.cache_clear()

    ensure_action_allowed("calendar_create_event", "Anything")
    ensure_action_allowed("calendar_create_event", None)


def teardown_function() -> None:
    load_settings.cache_clear()
