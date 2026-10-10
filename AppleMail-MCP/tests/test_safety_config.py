import pytest

from apple_mail_mcp.config import load_settings


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
    monkeypatch.setenv("APPLE_MAIL_MCP_SAFETY_PROFILE", value)
    assert settings().safety_profile == "safe_readonly"


@pytest.mark.parametrize("value", ["safe_readonly", "safe_manage", "full_access"])
def test_valid_safety_setting_is_preserved(monkeypatch, value):
    monkeypatch.setenv("APPLE_MAIL_MCP_SAFETY_PROFILE", value)
    assert settings().safety_profile == value


def test_unset_safety_setting_preserves_existing_default(monkeypatch):
    monkeypatch.delenv("APPLE_MAIL_MCP_SAFETY_PROFILE", raising=False)
    assert settings().safety_profile == "safe_manage"
