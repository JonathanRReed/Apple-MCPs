from apple_notes_mcp.config import load_settings
from apple_notes_mcp.permissions import SafetyError, ensure_action_allowed


def test_safe_readonly_blocks_write(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_NOTES_MCP_SAFETY_MODE", "safe_readonly")
    load_settings.cache_clear()

    try:
        ensure_action_allowed("notes_create_note", "iCloud", "Personal")
    except SafetyError as exc:
        assert exc.error_code == "WRITE_BLOCKED"
    else:
        raise AssertionError("Expected SafetyError")


def test_allowed_folder_blocks_unlisted_folder(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_NOTES_MCP_SAFETY_MODE", "full_access")
    monkeypatch.setenv("APPLE_NOTES_MCP_ALLOWED_FOLDERS", "Work,Personal")
    load_settings.cache_clear()

    try:
        ensure_action_allowed("notes_list_notes", "iCloud", "School")
    except SafetyError as exc:
        assert exc.error_code == "FOLDER_BLOCKED"
    else:
        raise AssertionError("Expected SafetyError")


def teardown_function() -> None:
    load_settings.cache_clear()
