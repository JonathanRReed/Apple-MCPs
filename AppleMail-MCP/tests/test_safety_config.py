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


def test_send_block_names_env_var_value_and_fix(monkeypatch):
    from apple_mail_mcp.config import Settings
    from apple_mail_mcp.models import SafetyProfile
    from apple_mail_mcp.tools import mail_send_message

    monkeypatch.setenv("APPLE_MAIL_MCP_SAFETY_PROFILE", "safe_manage")
    result = mail_send_message(to=["a@example.com"], settings=Settings(safety_profile=SafetyProfile.SAFE_MANAGE), bridge=object())  # type: ignore[arg-type]

    assert result.error_code == "SAFETY_POLICY_BLOCK"
    assert "APPLE_MAIL_MCP_SAFETY_PROFILE" in result.message
    assert "APPLE_MAIL_MCP_SAFETY_PROFILE=full_access" in result.suggestion
    assert '"Mail safety mode"' in result.suggestion
    assert "restart" in result.suggestion


def test_draft_block_in_readonly_suggests_safe_manage():
    from apple_mail_mcp.models import SafetyProfile
    from apple_mail_mcp.permissions import SafetyPolicyError, ensure_tool_allowed

    with pytest.raises(SafetyPolicyError) as caught:
        ensure_tool_allowed(SafetyProfile.SAFE_READONLY, "mail_compose_draft")
    assert "APPLE_MAIL_MCP_SAFETY_PROFILE=safe_manage" in caught.value.suggestion


@pytest.mark.parametrize(("value", "expected"), [("full_acess", "'full_acess'"), ("", "blank")])
def test_health_reports_invalid_safety_value(monkeypatch, value, expected):
    from apple_mail_mcp.tools import health_tool

    monkeypatch.setenv("APPLE_MAIL_MCP_SAFETY_PROFILE", value)
    result = health_tool(settings())

    assert result.safety_profile == "safe_readonly"
    assert expected in result.safety_mode_warning
    assert "APPLE_MAIL_MCP_SAFETY_PROFILE" in result.safety_mode_warning


@pytest.mark.parametrize("value", [None, "safe_manage", " full_access "])
def test_health_has_no_warning_for_valid_or_unset_values(monkeypatch, value):
    from apple_mail_mcp.tools import health_tool

    if value is None:
        monkeypatch.delenv("APPLE_MAIL_MCP_SAFETY_PROFILE", raising=False)
    else:
        monkeypatch.setenv("APPLE_MAIL_MCP_SAFETY_PROFILE", value)
    assert health_tool(settings()).safety_mode_warning is None
