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

    def list_settings_domains(self):
        return [
            {"domain": "NSGlobalDomain", "label": "Global Preferences"},
            {"domain": "com.apple.universalaccess", "label": "Accessibility"},
        ]

    def appearance_settings(self):
        return {"mode": "dark", "accent_color": 0, "highlight_color": "0.1 0.2 0.3 Other", "show_all_extensions": True}

    def accessibility_settings(self):
        return {"reduce_motion": False, "increase_contrast": False}

    def dock_settings(self):
        return {"autohide": True, "orientation": "left", "tile_size": 48}

    def finder_settings(self):
        return {"preferred_view_style": "Nlsv", "show_path_bar": True, "show_status_bar": True}

    def settings_snapshot(self):
        return {
            "appearance": self.appearance_settings(),
            "accessibility": self.accessibility_settings(),
            "dock": self.dock_settings(),
            "finder": self.finder_settings(),
        }

    def read_preference_domain(self, domain: str, current_host: bool = False):
        return {"domain": domain, "current_host": current_host, "sample": True}

    def set_appearance_mode(self, mode: str):
        return {"requested_value": mode, "observed_value": mode, "restarted_processes": []}

    def set_show_all_extensions(self, enabled: bool):
        return {"requested_value": enabled, "observed_value": enabled, "restarted_processes": []}

    def set_show_hidden_files(self, enabled: bool):
        return {"requested_value": enabled, "observed_value": enabled, "restarted_processes": ["Finder"]}

    def set_finder_path_bar(self, enabled: bool):
        return {"requested_value": enabled, "observed_value": enabled, "restarted_processes": ["Finder"]}

    def set_finder_status_bar(self, enabled: bool):
        return {"requested_value": enabled, "observed_value": enabled, "restarted_processes": ["Finder"]}

    def set_dock_autohide(self, enabled: bool):
        return {"requested_value": enabled, "observed_value": enabled, "restarted_processes": ["Dock"]}

    def set_dock_show_recents(self, enabled: bool):
        return {"requested_value": enabled, "observed_value": enabled, "restarted_processes": ["Dock"]}

    def set_reduce_motion(self, enabled: bool):
        return {"requested_value": enabled, "observed_value": enabled, "restarted_processes": []}

    def set_increase_contrast(self, enabled: bool):
        return {"requested_value": enabled, "observed_value": enabled, "restarted_processes": []}

    def set_reduce_transparency(self, enabled: bool):
        return {"requested_value": enabled, "observed_value": enabled, "restarted_processes": []}

    def gui_list_menu_bar_items(self, application: str | None = None):
        return ["Apple", "File", "Edit"]

    def gui_click_menu_path(self, menu_path: list[str], application: str | None = None):
        return application or "Mail"

    def gui_press_keys(self, key: str, modifiers: list[str] | None = None, application: str | None = None):
        return application or "Mail"

    def gui_type_text(self, text: str, application: str | None = None):
        return application or "Mail"

    def gui_click_button(self, label: str, application: str | None = None):
        return application or "Mail"

    def gui_choose_popup_value(self, label: str, value: str, application: str | None = None):
        return application or "Mail"


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


def test_system_get_settings_snapshot(monkeypatch):
    monkeypatch.setattr(tools, "_bridge", lambda: StubBridge())
    result = tools.system_get_settings_snapshot()
    assert result.ok is True
    assert result.appearance["mode"] == "dark"
    assert result.dock["autohide"] is True


def test_system_read_preference_domain(monkeypatch):
    monkeypatch.setattr(tools, "_bridge", lambda: StubBridge())
    result = tools.system_read_preference_domain("NSGlobalDomain", current_host=True)
    assert result.ok is True
    assert result.domain == "NSGlobalDomain"
    assert result.current_host is True
    assert result.values["sample"] is True


def test_system_list_settings_domains(monkeypatch):
    monkeypatch.setattr(tools, "_bridge", lambda: StubBridge())
    result = tools.system_list_settings_domains()
    assert result.ok is True
    assert result.count == 2
    assert result.domains[0]["domain"] == "NSGlobalDomain"


def test_system_setting_writes(monkeypatch):
    monkeypatch.setenv("APPLE_SYSTEM_MCP_SAFETY_MODE", "safe_manage")
    tools.load_settings.cache_clear()
    monkeypatch.setattr(tools, "_bridge", lambda: StubBridge())

    appearance = tools.system_set_appearance_mode("dark")
    hidden = tools.system_set_show_hidden_files(True)
    dock = tools.system_set_dock_autohide(False)

    assert appearance.ok is True
    assert appearance.observed_value == "dark"
    assert hidden.restarted_processes == ["Finder"]
    assert dock.setting == "autohide"
    assert dock.observed_value is False


def test_system_gui_fallback_tools(monkeypatch):
    monkeypatch.setenv("APPLE_SYSTEM_MCP_SAFETY_MODE", "safe_manage")
    tools.load_settings.cache_clear()
    monkeypatch.setattr(tools, "_bridge", lambda: StubBridge())

    menu_items = tools.system_gui_list_menu_bar_items("Mail")
    click_result = tools.system_gui_click_menu_path(["File", "New Viewer"], application="Mail")
    type_result = tools.system_gui_type_text("hello", application="Mail")

    assert menu_items.ok is True
    assert menu_items.used_gui_fallback is True
    assert menu_items.count == 3
    assert click_result.target == "File > New Viewer"
    assert click_result.used_gui_fallback is True
    assert type_result.value == "hello"


def teardown_function():
    tools.load_settings.cache_clear()


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
