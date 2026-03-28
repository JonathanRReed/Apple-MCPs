from apple_messages_mcp.config import load_settings
from apple_messages_mcp.permissions import SafetyError, ensure_action_allowed


def test_safe_readonly_blocks_send(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_MESSAGES_MCP_SAFETY_MODE", "safe_readonly")
    load_settings.cache_clear()

    try:
        ensure_action_allowed("messages_send_message")
    except SafetyError as exc:
        assert exc.error_code == "WRITE_BLOCKED"
    else:
        raise AssertionError("Expected SafetyError")


def teardown_function() -> None:
    load_settings.cache_clear()
