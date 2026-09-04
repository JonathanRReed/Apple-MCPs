import asyncio
import json
import os
import select
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from apple_mcp_common.runtime import notify_resource_updated, notify_resources_changed, require_loopback_host


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "127.42.0.9", "::1"])
def test_require_loopback_host_accepts_local_addresses(host: str) -> None:
    assert require_loopback_host(host) == host


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.2", "example.com", ""])
def test_require_loopback_host_rejects_network_exposure(host: str) -> None:
    with pytest.raises(ValueError, match="loopback"):
        require_loopback_host(host)


class StubSession:
    def __init__(self, protocol_version: str) -> None:
        self.protocol_version = protocol_version
        self.updated: list[str] = []
        self.list_changed = 0

    async def send_resource_updated(self, uri: str) -> None:
        self.updated.append(uri)

    async def send_resource_list_changed(self) -> None:
        self.list_changed += 1


class StubContext:
    def __init__(self, protocol_version: str) -> None:
        self.protocol_version = protocol_version
        self.request_context = type("RequestContext", (), {"session": StubSession(protocol_version)})()
        self.modern_updated: list[str] = []
        self.modern_list_changed = 0

    async def notify_resource_updated(self, uri: str) -> None:
        self.modern_updated.append(uri)

    async def notify_resources_changed(self) -> None:
        self.modern_list_changed += 1


def test_resource_notifications_use_modern_subscription_bus() -> None:
    context = StubContext("2026-07-28")

    asyncio.run(notify_resource_updated(context, "apple://test"))
    asyncio.run(notify_resources_changed(context))

    assert context.modern_updated == ["apple://test"]
    assert context.modern_list_changed == 1
    assert context.request_context.session.updated == []
    assert context.request_context.session.list_changed == 0


def test_resource_notifications_use_legacy_session_api() -> None:
    context = StubContext("2025-11-25")

    asyncio.run(notify_resource_updated(context, "apple://test"))
    asyncio.run(notify_resources_changed(context))

    assert context.modern_updated == []
    assert context.modern_list_changed == 0
    assert context.request_context.session.updated == ["apple://test"]
    assert context.request_context.session.list_changed == 1


def test_legacy_resource_notifications_cross_stdio_wire() -> None:
    protocol_version = "2025-11-25"
    server_source = textwrap.dedent(
        """
        from mcp.server.mcpserver import Context, MCPServer
        from apple_mcp_common.runtime import notify_resource_updated, notify_resources_changed

        server = MCPServer("notification-wire-test")

        @server.tool()
        async def trigger(ctx: Context) -> str:
            await notify_resource_updated(ctx, "apple://wire-test")
            await notify_resources_changed(ctx)
            return "sent"

        server.run()
        """
    )
    environment = os.environ.copy()
    common_source = str(Path(__file__).resolve().parents[1] / "src")
    environment["PYTHONPATH"] = common_source
    process = subprocess.Popen(
        [sys.executable, "-c", server_source],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    try:
        messages = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": protocol_version,
                    "capabilities": {},
                    "clientInfo": {"name": "wire-test", "version": "1"},
                },
            },
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "trigger", "arguments": {}}},
        ]
        for message in messages:
            process.stdin.write(json.dumps(message) + "\n")
        process.stdin.flush()

        received = []
        wire_buffer = b""
        deadline = time.monotonic() + 20
        while len(received) < 4:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([process.stdout], [], [], remaining)[0]:
                raise AssertionError(f"Timed out waiting for wire messages: {received!r}")
            chunk = os.read(process.stdout.fileno(), 65536)
            assert chunk, f"Server closed stdout before sending all messages: {received!r}"
            wire_buffer += chunk
            while b"\n" in wire_buffer:
                line, wire_buffer = wire_buffer.split(b"\n", 1)
                received.append(json.loads(line))
        initialize_result = next(message["result"] for message in received if message.get("id") == 1)
        assert initialize_result["protocolVersion"] == protocol_version
        updated = next(message for message in received if message.get("method") == "notifications/resources/updated")
        assert updated["params"]["uri"] == "apple://wire-test"
        assert any(message.get("method") == "notifications/resources/list_changed" for message in received)
        assert any(message.get("id") == 2 and "result" in message for message in received)
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
