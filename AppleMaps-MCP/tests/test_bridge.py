from pathlib import Path
import subprocess

import pytest

from apple_maps_mcp.maps_bridge import AppleMapsBridge, MapsBridgeError


def test_run_helper_maps_timeout_to_structured_error(monkeypatch) -> None:
    bridge = AppleMapsBridge(Path("/tmp/apple_maps_bridge.swift"), Path("/tmp/apple-maps-bridge"))

    monkeypatch.setattr(bridge, "_ensure_helper", lambda: None)

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="apple-maps-bridge", timeout=20)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(MapsBridgeError) as exc_info:
        bridge.search_places("coffee")

    assert exc_info.value.error_code == "HELPER_TIMEOUT"
