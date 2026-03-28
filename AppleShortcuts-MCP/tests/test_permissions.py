from apple_shortcuts_mcp.config import load_settings
from apple_shortcuts_mcp.permissions import SafetyError, ensure_action_allowed


def test_safe_readonly_blocks_run(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_SHORTCUTS_MCP_SAFETY_MODE", "safe_readonly")
    load_settings.cache_clear()

    try:
        ensure_action_allowed("shortcuts_run_shortcut")
    except SafetyError as exc:
        assert exc.error_code == "WRITE_BLOCKED"
    else:
        raise AssertionError("Expected SafetyError")


def test_read_actions_allowed_in_safe_manage(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_SHORTCUTS_MCP_SAFETY_MODE", "safe_manage")
    load_settings.cache_clear()

    ensure_action_allowed("shortcuts_list_shortcuts")


def teardown_function() -> None:
    load_settings.cache_clear()
