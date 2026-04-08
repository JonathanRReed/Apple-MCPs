from apple_system_mcp.system_bridge import SystemBridge, SystemBridgeError


def test_context_snapshot_degrades_when_frontmost_lookup_times_out(monkeypatch) -> None:
    bridge = SystemBridge()

    class Battery:
        def model_dump(self):
            return {"percentage": 88, "raw": "battery"}

    monkeypatch.setattr(bridge, "battery", lambda: Battery())
    monkeypatch.setattr(
        bridge,
        "frontmost_application",
        lambda: (_ for _ in ()).throw(SystemBridgeError("COMMAND_TIMEOUT", "timed out")),
    )
    monkeypatch.setattr(bridge, "running_apps", lambda: [])
    monkeypatch.setattr(
        bridge,
        "focus_status",
        lambda: {
            "focus_supported": False,
            "focus_active": None,
            "focus_name": None,
            "observed_at": "2026-04-07T16:00:00-05:00",
            "source": "unsupported_local_install",
            "confidence": 0.0,
            "notes": [],
        },
    )

    snapshot = bridge.context_snapshot()

    assert snapshot["battery"]["percentage"] == 88
    assert snapshot["frontmost_app"] is None
    assert any("Frontmost application unavailable" in note for note in snapshot["notification_history_notes"])
