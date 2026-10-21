import pytest

from apple_mcp_common.bundle import drop_unexpanded_user_config
from apple_mcp_common.safety import SAFETY_SETTING_TITLES, safety_block_suggestion, safety_mode_warning

ENV = "APPLE_MAIL_MCP_SAFETY_PROFILE"


def test_block_suggestion_names_env_var_value_desktop_setting_and_restart() -> None:
    text = safety_block_suggestion(ENV, "full_access")
    assert f"{ENV}=full_access" in text
    assert '"env" block' in text
    assert 'Claude Desktop' in text and '"Mail safety mode" to full_access' in text
    assert "restart the MCP client" in text
    assert "Ask the user" in text


def test_block_suggestion_for_manage_mentions_both_sufficient_modes() -> None:
    text = safety_block_suggestion("APPLE_NOTES_MCP_SAFETY_MODE", "safe_manage")
    assert "safe_manage or full_access" in text
    assert "APPLE_NOTES_MCP_SAFETY_MODE=safe_manage" in text


def test_block_suggestion_explains_a_typo_first(monkeypatch) -> None:
    monkeypatch.setenv(ENV, "full-access")
    text = safety_block_suggestion(ENV, "full_access", "safe_readonly")
    assert text.startswith(f"{ENV} is set to 'full-access'")
    assert "fell back to safe_readonly" in text


@pytest.mark.parametrize(
    ("raw", "effective", "expected"),
    [
        (None, "safe_manage", None),
        ("safe_manage", "safe_manage", None),
        ("  full_access ", "full_access", None),
        ("SAFE_MANAGE", "safe_manage", None),  # accepted case-insensitively by Files/System
        ("full_access", "safe_manage", None),  # valid value; injected settings may differ
        ("SAFE_MANAGE", "safe_readonly", "'SAFE_MANAGE'"),  # case-sensitive servers coerce it
        ("safe_mange", "safe_readonly", "'safe_mange'"),
        ("", "safe_readonly", "set but blank"),
        ("   ", "safe_readonly", "set but blank"),
        ("${user_config.mail_safety_mode}", "safe_readonly", "not a valid safety mode"),
    ],
)
def test_safety_mode_warning(raw, effective, expected) -> None:
    environ = {} if raw is None else {ENV: raw}
    warning = safety_mode_warning(ENV, effective, environ)
    if expected is None:
        assert warning is None
    else:
        assert expected in warning
        assert f"fell back to {effective}" in warning
        assert "safe_readonly, safe_manage, full_access" in warning


def test_every_safety_env_var_has_a_desktop_title() -> None:
    assert len(SAFETY_SETTING_TITLES) == 9
    assert all(title.endswith("safety mode") for title in SAFETY_SETTING_TITLES.values())


def test_drop_unexpanded_user_config_removes_only_literal_placeholders() -> None:
    environ = {
        "APPLE_MAIL_MCP_ALLOWED_ATTACHMENT_ROOT": "${user_config.mail_allowed_attachment_root}",
        "APPLE_FILES_MCP_ALLOWED_ROOTS": "~/Desktop",
        "APPLE_CALENDAR_MCP_ALLOWED_CALENDARS": "",
        "OTHER": "${user_config.other}",
    }
    removed = drop_unexpanded_user_config(environ)
    assert removed == ["APPLE_MAIL_MCP_ALLOWED_ATTACHMENT_ROOT"]
    assert environ == {
        "APPLE_FILES_MCP_ALLOWED_ROOTS": "~/Desktop",
        "APPLE_CALENDAR_MCP_ALLOWED_CALENDARS": "",
        "OTHER": "${user_config.other}",
    }
