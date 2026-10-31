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


def test_allowed_roots_follow_shortcuts_then_files_setting(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("APPLE_SHORTCUTS_MCP_ALLOWED_ROOTS", raising=False)
    monkeypatch.setenv("APPLE_FILES_MCP_ALLOWED_ROOTS", f"{tmp_path / 'files'}, ")
    load_settings.cache_clear()
    assert load_settings().allowed_roots == (tmp_path / "files",)

    monkeypatch.setenv("APPLE_SHORTCUTS_MCP_ALLOWED_ROOTS", f"{tmp_path / 'a'},{tmp_path / 'b'}")
    load_settings.cache_clear()
    assert load_settings().allowed_roots == (tmp_path / "a", tmp_path / "b")


def test_allowed_roots_default_to_downloads(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("APPLE_SHORTCUTS_MCP_ALLOWED_ROOTS", raising=False)
    monkeypatch.delenv("APPLE_FILES_MCP_ALLOWED_ROOTS", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    load_settings.cache_clear()
    assert load_settings().allowed_roots == (tmp_path / "Downloads",)
