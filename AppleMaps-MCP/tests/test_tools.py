from apple_maps_mcp import tools


class StubBridge:
    def helper_available(self):
        return True, True

    def search_places(self, query: str, limit: int = 5):
        return {"places": [{"name": "Coffee Shop", "address": "123 Main St", "latitude": 30.0, "longitude": -97.0, "phone": None, "url": None}]}

    def directions(self, origin: str, destination: str, transport: str = "driving"):
        return {
            "origin": {"name": origin, "address": origin, "latitude": 30.0, "longitude": -97.0, "phone": None, "url": None},
            "destination": {"name": destination, "address": destination, "latitude": 30.1, "longitude": -97.1, "phone": None, "url": None},
            "transport": transport,
            "distance_meters": 1000,
            "expected_travel_time_seconds": 600,
            "advisory_notices": [],
            "maps_url": "https://maps.apple.com/?daddr=Coffee+Shop",
        }

    def maps_url(self, destination: str, origin: str | None = None, transport: str = "driving"):
        return "https://maps.apple.com/?daddr=Coffee+Shop"


def test_maps_search_places(monkeypatch):
    monkeypatch.setattr(tools, "_bridge", lambda: StubBridge())
    result = tools.maps_search_places("coffee")
    assert result.ok is True
    assert result.count == 1
    assert result.places[0].name == "Coffee Shop"


def test_maps_build_maps_link(monkeypatch):
    monkeypatch.setattr(tools, "_bridge", lambda: StubBridge())
    result = tools.maps_build_maps_link("Coffee Shop")
    assert result.url.startswith("https://maps.apple.com/")


def test_maps_status_resource(monkeypatch):
    monkeypatch.setattr(tools, "_bridge", lambda: StubBridge())
    payload = tools.maps_status_resource()
    assert "\"helper_available\": true" in payload
    assert "\"driving\"" in payload


def test_main_uses_streamable_http(monkeypatch):
    monkeypatch.setenv("APPLE_MAPS_MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("APPLE_MAPS_MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("APPLE_MAPS_MCP_PORT", "8765")
    monkeypatch.setenv("APPLE_MAPS_MCP_LOG_LEVEL", "DEBUG")
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
