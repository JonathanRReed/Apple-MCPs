from apple_contacts_mcp.config import load_settings


def test_load_settings_uses_packaged_applescripts() -> None:
    load_settings.cache_clear()

    try:
        settings = load_settings()
    finally:
        load_settings.cache_clear()

    assert settings.scripts_dir.name == "applescripts"
    assert settings.scripts_dir.parent.name == "apple_contacts_mcp"
    assert settings.scripts_dir.exists()
