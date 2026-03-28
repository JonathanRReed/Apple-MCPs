import os

from apple_mail_mcp.config import load_settings


def test_load_settings_defaults_invalid_transport_to_stdio() -> None:
    previous_transport = os.environ.get("APPLE_MAIL_MCP_TRANSPORT")
    os.environ["APPLE_MAIL_MCP_TRANSPORT"] = "invalid"

    try:
        settings = load_settings()
    finally:
        if previous_transport is None:
            os.environ.pop("APPLE_MAIL_MCP_TRANSPORT", None)
        else:
            os.environ["APPLE_MAIL_MCP_TRANSPORT"] = previous_transport

    assert settings.transport == "stdio"
