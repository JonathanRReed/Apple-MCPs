from apple_files_mcp import tools
from apple_files_mcp.models import FileEntry


class StubBridge:
    def list_allowed_roots(self):
        return ["/Users/test/Downloads"]

    def list_directory(self, path: str):
        return [FileEntry(path=f"{path}/a.txt", name="a.txt", parent=path, is_directory=False, size_bytes=12, modified_at="2026-04-01T00:00:00Z", extension=".txt")]

    def search_files(self, query: str, base_path: str | None = None, limit: int = 25):
        return [FileEntry(path="/Users/test/Downloads/a.txt", name="a.txt", parent="/Users/test/Downloads", is_directory=False, size_bytes=12, modified_at="2026-04-01T00:00:00Z", extension=".txt")]

    def file_info(self, path: str):
        return FileEntry(path=path, name="a.txt", parent="/Users/test/Downloads", is_directory=False, size_bytes=12, modified_at="2026-04-01T00:00:00Z", extension=".txt")

    def read_text_file(self, path: str, max_bytes: int = 100_000):
        return ("hello", False)

    def recent_files(self, limit: int = 25):
        return [FileEntry(path="/Users/test/Downloads/a.txt", name="a.txt", parent="/Users/test/Downloads", is_directory=False, size_bytes=12, modified_at="2026-04-01T00:00:00Z", extension=".txt")]

    def open_path(self, path: str):
        return path

    def reveal_in_finder(self, path: str):
        return path

    def get_tags(self, path: str):
        return path, ["Work", "Important"], False

    def set_tags(self, path: str, tags: list[str]):
        return path, tags, False

    def add_tags(self, path: str, tags: list[str]):
        return path, ["Existing", *tags], False

    def remove_tags(self, path: str, tags: list[str]):
        return path, ["Existing"], False

    def list_recent_locations(self, limit: int = 15):
        return [FileEntry(path="/Users/test/Downloads", name="Downloads", parent="/Users/test", is_directory=True, modified_at="2026-04-01T00:00:00Z", location_kind="local")]

    def icloud_status(self):
        return {
            "available": True,
            "root_path": "/Users/test/Library/Mobile Documents/com~apple~CloudDocs",
            "allowed_root_present": True,
            "allowed_roots": [
                {"path": "/Users/test/Downloads", "is_icloud": False, "location_kind": "local"},
                {"path": "/Users/test/Library/Mobile Documents/com~apple~CloudDocs", "is_icloud": True, "location_kind": "icloud"},
            ],
        }

    def create_folder(self, path: str):
        return path

    def move_path(self, source: str, destination: str):
        return source, destination

    def delete_path(self, path: str):
        return path


def test_files_health(monkeypatch):
    monkeypatch.setenv("APPLE_FILES_MCP_SAFETY_MODE", "safe_readonly")
    tools.load_settings.cache_clear()
    monkeypatch.setattr(tools, "_bridge", lambda: StubBridge())
    result = tools.files_health()
    assert result.server_name == "Apple Files MCP"
    assert "list_directory" in result.capabilities
    assert "get_tags" in result.capabilities
    assert "get_icloud_status" in result.capabilities
    assert "create_folder" not in result.capabilities
    assert "delete_path" not in result.capabilities
    assert "streamable-http" in result.supports


def test_files_health_respects_safety_mode(monkeypatch):
    monkeypatch.setenv("APPLE_FILES_MCP_SAFETY_MODE", "safe_manage")
    tools.load_settings.cache_clear()
    monkeypatch.setattr(tools, "_bridge", lambda: StubBridge())

    manage = tools.files_health()

    assert "create_folder" in manage.capabilities
    assert "move_path" in manage.capabilities
    assert "open_path" in manage.capabilities
    assert "set_tags" in manage.capabilities
    assert "delete_path" not in manage.capabilities

    monkeypatch.setenv("APPLE_FILES_MCP_SAFETY_MODE", "full_access")
    tools.load_settings.cache_clear()

    full = tools.files_health()

    assert "delete_path" in full.capabilities


def test_files_read_text_file(monkeypatch):
    monkeypatch.setattr(tools, "_bridge", lambda: StubBridge())
    result = tools.files_read_text_file("/Users/test/Downloads/a.txt")
    assert result.ok is True
    assert result.text == "hello"


def test_files_search_files(monkeypatch):
    monkeypatch.setattr(tools, "_bridge", lambda: StubBridge())
    result = tools.files_search_files("a")
    assert result.ok is True
    assert result.count == 1


def test_files_tags_and_icloud_status(monkeypatch):
    monkeypatch.setenv("APPLE_FILES_MCP_SAFETY_MODE", "safe_manage")
    tools.load_settings.cache_clear()
    monkeypatch.setattr(tools, "_bridge", lambda: StubBridge())

    tags = tools.files_get_tags("/Users/test/Downloads/a.txt")
    updated = tools.files_add_tags("/Users/test/Downloads/a.txt", ["Urgent"])
    icloud = tools.files_get_icloud_status()

    assert tags.ok is True
    assert tags.tags == ["Work", "Important"]
    assert updated.ok is True
    assert "Urgent" in updated.tags
    assert icloud.ok is True
    assert icloud.available is True
    assert icloud.allowed_root_present is True


def test_files_open_and_recent_locations(monkeypatch):
    monkeypatch.setenv("APPLE_FILES_MCP_SAFETY_MODE", "safe_manage")
    tools.load_settings.cache_clear()
    monkeypatch.setattr(tools, "_bridge", lambda: StubBridge())

    opened = tools.files_open_path("/Users/test/Downloads/a.txt")
    revealed = tools.files_reveal_in_finder("/Users/test/Downloads/a.txt")
    locations = tools.files_list_recent_locations()

    assert opened.ok is True
    assert opened.action == "opened"
    assert revealed.ok is True
    assert revealed.revealed is True
    assert locations.ok is True
    assert locations.count == 1
    assert locations.locations[0].is_directory is True


def test_main_uses_streamable_http(monkeypatch):
    monkeypatch.setenv("APPLE_FILES_MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("APPLE_FILES_MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("APPLE_FILES_MCP_PORT", "8765")
    monkeypatch.setenv("APPLE_FILES_MCP_LOG_LEVEL", "DEBUG")
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


def teardown_function():
    tools.load_settings.cache_clear()
