from apple_reminders_mcp.config import load_settings


def test_load_settings_uses_packaged_helper_source() -> None:
    load_settings.cache_clear()

    try:
        settings = load_settings()
    finally:
        load_settings.cache_clear()

    assert settings.helper_source.name == "apple_pim_bridge.swift"
    assert settings.helper_source.parent.name == "apple_reminders_mcp"
    assert settings.helper_source.exists()
    assert settings.helper_binary.name == "apple-reminders-pim-bridge"
