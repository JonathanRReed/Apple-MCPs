import pytest

from apple_notes_mcp.config import load_settings


def settings():
    if hasattr(load_settings, "cache_clear"):
        load_settings.cache_clear()
    try:
        return load_settings()
    finally:
        if hasattr(load_settings, "cache_clear"):
            load_settings.cache_clear()


@pytest.mark.parametrize("value", ["safe_readony", "", "   ", "invalid"])
def test_explicit_invalid_safety_setting_is_readonly(monkeypatch, value):
    monkeypatch.setenv("APPLE_NOTES_MCP_SAFETY_MODE", value)
    assert settings().safety_mode == "safe_readonly"


@pytest.mark.parametrize("value", ["safe_readonly", "safe_manage", "full_access"])
def test_valid_safety_setting_is_preserved(monkeypatch, value):
    monkeypatch.setenv("APPLE_NOTES_MCP_SAFETY_MODE", value)
    assert settings().safety_mode == value


def test_unset_safety_setting_preserves_existing_default(monkeypatch):
    monkeypatch.delenv("APPLE_NOTES_MCP_SAFETY_MODE", raising=False)
    assert settings().safety_mode == "full_access"


@pytest.mark.parametrize(
    ("action", "mode", "required"),
    [
        ('notes_create_note', 'safe_readonly', 'safe_manage'),
    ],
)
def test_safety_block_names_env_var_value_and_fix(monkeypatch, action, mode, required):
    from apple_notes_mcp.permissions import SafetyError, ensure_action_allowed

    monkeypatch.setenv("APPLE_NOTES_MCP_SAFETY_MODE", mode)
    load_settings.cache_clear()
    try:
        with pytest.raises(SafetyError) as caught:
            ensure_action_allowed(action)
    finally:
        load_settings.cache_clear()
    assert "APPLE_NOTES_MCP_SAFETY_MODE" in caught.value.message
    suggestion = caught.value.suggestion
    assert f"APPLE_NOTES_MCP_SAFETY_MODE={required}" in suggestion
    assert "Claude Desktop" in suggestion
    assert "restart" in suggestion


def test_safety_block_explains_an_invalid_value(monkeypatch):
    from apple_notes_mcp.permissions import SafetyError, ensure_action_allowed

    monkeypatch.setenv("APPLE_NOTES_MCP_SAFETY_MODE", "safe-manage")
    load_settings.cache_clear()
    try:
        with pytest.raises(SafetyError) as caught:
            ensure_action_allowed("notes_create_note")
    finally:
        load_settings.cache_clear()
    assert "'safe-manage'" in caught.value.suggestion
    assert "fell back to safe_readonly" in caught.value.suggestion
