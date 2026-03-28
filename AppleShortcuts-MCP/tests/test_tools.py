from apple_shortcuts_mcp.config import load_settings
from apple_shortcuts_mcp.models import ShortcutFolderInfo, ShortcutInfo, ShortcutRunResponse
from apple_shortcuts_mcp import tools


class FakeBridge:
    def cli_available(self) -> bool:
        return True

    def list_shortcuts(self, folder_name: str | None = None):
        if folder_name == "Home":
            return [
                ShortcutInfo(name="Open Trunk", identifier="9A2D4AFE-D4B5-418E-814A-DB97BAB3BE4D", folder_name="Home"),
            ]
        return [
            ShortcutInfo(name="Open Trunk", identifier="9A2D4AFE-D4B5-418E-814A-DB97BAB3BE4D", folder_name="Home"),
            ShortcutInfo(name="Start Car", identifier="29B15189-C4FC-4823-89AE-45617D461CBA", folder_name="Car"),
        ]

    def list_folders(self):
        return [ShortcutFolderInfo(folder_name="Home", shortcut_count=1), ShortcutFolderInfo(folder_name="Car", shortcut_count=1)]

    def view_shortcut(self, shortcut_name_or_identifier: str):
        return ShortcutInfo(name="Open Trunk", identifier="9A2D4AFE-D4B5-418E-814A-DB97BAB3BE4D", folder_name="Home")

    def run_shortcut(self, shortcut_name_or_identifier: str, input_paths=None, output_path=None, output_type=None):
        return ShortcutRunResponse(
            shortcut_name="Open Trunk",
            shortcut_identifier="9A2D4AFE-D4B5-418E-814A-DB97BAB3BE4D",
            exit_code=0,
            stdout="done",
            stderr="",
            artifacts=[],
        )

    def shortcuts_snapshot(self):
        return {
            "folders": [folder.model_dump() for folder in self.list_folders()],
            "shortcuts": [shortcut.model_dump() for shortcut in self.list_shortcuts()],
            "count": 2,
        }

    def shortcuts_folder_snapshot(self, folder_name: str):
        shortcuts = self.list_shortcuts(folder_name=folder_name)
        return {
            "folder_name": folder_name,
            "shortcuts": [shortcut.model_dump() for shortcut in shortcuts],
            "count": len(shortcuts),
        }


def test_health_tool_reports_capabilities(monkeypatch) -> None:
    load_settings.cache_clear()
    monkeypatch.setenv("APPLE_SHORTCUTS_MCP_SAFETY_MODE", "full_access")
    monkeypatch.setenv("APPLE_SHORTCUTS_MCP_SHORTCUTS_COMMAND", "shortcuts")
    load_settings.cache_clear()

    result = tools.health_tool(load_settings())

    assert result.ok is True
    assert result.permissions.shortcuts_cli_available is True
    assert "run_shortcuts" in result.capabilities


def test_list_shortcuts_returns_structured_payload(monkeypatch) -> None:
    monkeypatch.setattr(tools, "_bridge", lambda: FakeBridge())

    result = tools.shortcuts_list_shortcuts_tool()

    assert result.count == 2
    assert result.shortcuts[0].identifier is not None


def test_run_shortcut_returns_structured_payload(monkeypatch) -> None:
    monkeypatch.setattr(tools, "_bridge", lambda: FakeBridge())

    result = tools.shortcuts_run_shortcut_tool("Open Trunk", input_paths=["/etc/hosts"])

    assert result.ok is True
    assert result.shortcut_name == "Open Trunk"
    assert result.exit_code == 0


def test_resource_rendering(monkeypatch) -> None:
    monkeypatch.setattr(tools, "_bridge", lambda: FakeBridge())

    all_snapshot = tools.shortcuts_all_resource()
    folder_snapshot = tools.shortcuts_folder_resource("Home")

    assert "Open Trunk" in all_snapshot
    assert "Home" in folder_snapshot


def teardown_function() -> None:
    load_settings.cache_clear()
