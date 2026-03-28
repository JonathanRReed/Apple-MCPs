from apple_mail_mcp.models import SafetyProfile
from apple_mail_mcp.permissions import SafetyPolicyError, ensure_tool_allowed


def test_safe_manage_allows_compose_draft() -> None:
    ensure_tool_allowed(SafetyProfile.SAFE_MANAGE, "mail_compose_draft")


def test_safe_readonly_blocks_compose_draft() -> None:
    try:
        ensure_tool_allowed(SafetyProfile.SAFE_READONLY, "mail_compose_draft")
    except SafetyPolicyError as exc:
        assert "blocked" in str(exc)
        return

    raise AssertionError("safe_readonly should block compose")
