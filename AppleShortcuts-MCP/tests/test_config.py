from apple_shortcuts_mcp.config import load_settings


def test_load_settings_defaults(monkeypatch) -> None:
    monkeypatch.delenv("APPLE_SHORTCUTS_MCP_SAFETY_MODE", raising=False)
    monkeypatch.delenv("APPLE_SHORTCUTS_MCP_LOG_LEVEL", raising=False)
    monkeypatch.delenv("APPLE_SHORTCUTS_MCP_SHORTCUTS_COMMAND", raising=False)
    load_settings.cache_clear()

    settings = load_settings()

    assert settings.safety_mode == "full_access"
    assert settings.shortcuts_command == "shortcuts"


def teardown_function() -> None:
    load_settings.cache_clear()
