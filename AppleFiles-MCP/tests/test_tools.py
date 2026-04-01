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

    def create_folder(self, path: str):
        return path

    def move_path(self, source: str, destination: str):
        return source, destination

    def delete_path(self, path: str):
        return path


def test_files_health(monkeypatch):
    monkeypatch.setattr(tools, "_bridge", lambda: StubBridge())
    result = tools.files_health()
    assert result.server_name == "Apple Files MCP"
    assert "list_directory" in result.capabilities
    assert "streamable-http" in result.supports


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
