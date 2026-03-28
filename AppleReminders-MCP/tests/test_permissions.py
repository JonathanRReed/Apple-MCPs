from apple_reminders_mcp.config import load_settings
from apple_reminders_mcp.permissions import SafetyError, ensure_action_allowed


def test_safe_readonly_blocks_write(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_REMINDERS_MCP_SAFETY_MODE", "safe_readonly")
    load_settings.cache_clear()

    try:
        ensure_action_allowed("reminders_create_reminder", "Chores")
    except SafetyError as exc:
        assert exc.error_code == "WRITE_BLOCKED"
    else:
        raise AssertionError("Expected SafetyError")


def test_allowed_lists_blocks_unlisted_list(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_REMINDERS_MCP_SAFETY_MODE", "safe_manage")
    monkeypatch.setenv("APPLE_REMINDERS_MCP_ALLOWED_LISTS", "Work,Chores")
    load_settings.cache_clear()

    try:
        ensure_action_allowed("reminders_list_reminders", "School")
    except SafetyError as exc:
        assert exc.error_code == "LIST_BLOCKED"
    else:
        raise AssertionError("Expected SafetyError")


def teardown_function() -> None:
    load_settings.cache_clear()
