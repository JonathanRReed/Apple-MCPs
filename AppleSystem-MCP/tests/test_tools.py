from apple_system_mcp import tools
from apple_system_mcp.models import AppRecord, BatteryStatus


class StubBridge:
    def battery(self):
        return BatteryStatus(percentage=85, power_source="AC Power", charging=True, raw="now drawing from 'AC Power'")

    def frontmost_app(self):
        return "Mail"

    def running_apps(self):
        return [AppRecord(name="Mail"), AppRecord(name="Notes")]

    def get_clipboard(self):
        return "hello"

    def set_clipboard(self, text: str):
        self.last_clipboard = text

    def show_notification(self, title: str, body: str, subtitle: str | None = None):
        self.last_notification = (title, body, subtitle)

    def open_application(self, application: str):
        self.last_application = application


def test_system_status(monkeypatch):
    monkeypatch.setattr(tools, "_bridge", lambda: StubBridge())
    result = tools.system_status()
    assert result.ok is True
    assert result.frontmost_app == "Mail"
    assert result.running_apps_count == 2


def test_system_get_clipboard(monkeypatch):
    monkeypatch.setattr(tools, "_bridge", lambda: StubBridge())
    result = tools.system_get_clipboard()
    assert result.ok is True
    assert result.text == "hello"


def test_main_uses_streamable_http(monkeypatch):
    monkeypatch.setenv("APPLE_SYSTEM_MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("APPLE_SYSTEM_MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("APPLE_SYSTEM_MCP_PORT", "8765")
    monkeypatch.setenv("APPLE_SYSTEM_MCP_LOG_LEVEL", "DEBUG")
    tools.load_settings.cache_clear()

    captured = {}

    def fake_run(*, transport: str):
        captured["transport"] = transport
        captured["host"] = tools.mcp.settings.host
        captured["port"] = tools.mcp.settings.port
        captured["log_level"] = tools.mcp.settings.log_level

    monkeypatch.setattr(tools.mcp, "run", fake_run)

    tools.main()

    assert captured == {"transport": "streamable-http", "host": "0.0.0.0", "port": 8765, "log_level": "DEBUG"}
