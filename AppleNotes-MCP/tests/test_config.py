from apple_notes_mcp.config import DEFAULT_SCRIPT_TIMEOUT_SECONDS, load_settings


def test_load_settings_uses_packaged_applescripts() -> None:
    load_settings.cache_clear()

    try:
        settings = load_settings()
    finally:
        load_settings.cache_clear()

    assert settings.scripts_dir.name == "applescripts"
    assert settings.scripts_dir.parent.name == "apple_notes_mcp"
    assert settings.scripts_dir.exists()
    assert settings.script_timeout_seconds == DEFAULT_SCRIPT_TIMEOUT_SECONDS


def test_load_settings_reads_script_timeout_from_env(monkeypatch) -> None:
    load_settings.cache_clear()
    monkeypatch.setenv("APPLE_NOTES_MCP_SCRIPT_TIMEOUT_SECONDS", "120")

    try:
        assert load_settings().script_timeout_seconds == 120
    finally:
        load_settings.cache_clear()


def test_load_settings_rejects_invalid_script_timeout(monkeypatch) -> None:
    load_settings.cache_clear()
    monkeypatch.setenv("APPLE_NOTES_MCP_SCRIPT_TIMEOUT_SECONDS", "0")

    try:
        assert load_settings().script_timeout_seconds == DEFAULT_SCRIPT_TIMEOUT_SECONDS
    finally:
        load_settings.cache_clear()
