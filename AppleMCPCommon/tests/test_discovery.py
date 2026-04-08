from __future__ import annotations

import asyncio
from pathlib import Path

from mcp import types
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from apple_mcp_common.discovery import install_search_first_discovery


def test_install_search_first_discovery_minimizes_tool_list() -> None:
    mcp = FastMCP("Test")

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True), structured_output=True)
    def test_health() -> dict[str, bool]:
        return {"ok": True}

    @mcp.tool(structured_output=True)
    def test_write(value: str) -> dict[str, str]:
        return {"value": value}

    discovery = install_search_first_discovery(
        mcp,
        server_name="Test",
        domain="files",
        visible_tool_names={"test_health"},
    )

    async def load() -> tuple[list[types.Tool], dict[str, object]]:
        result = await mcp._mcp_server.request_handlers[types.ListToolsRequest](None)
        info_result = await mcp._mcp_server.request_handlers[types.CallToolRequest](
            types.CallToolRequest(
                params=types.CallToolRequestParams(
                    name="get_tool_info",
                    arguments={"name": "test_write"},
                )
            )
        )
        return result.root.tools, info_result.root.structuredContent

    visible_tools, info = asyncio.run(load())

    assert {tool.name for tool in visible_tools} == {"get_tool_info", "search_tools", "test_health"}
    assert info["ok"] is True
    assert info["name"] == "test_write"
    assert discovery.server_name == "Test"


def test_search_tools_returns_ranked_results() -> None:
    mcp = FastMCP("Test")

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True), structured_output=True)
    def files_search_files(query: str) -> dict[str, str]:
        return {"query": query}

    install_search_first_discovery(mcp, server_name="Test", domain="files")

    async def run_search() -> dict[str, object]:
        result = await mcp._mcp_server.request_handlers[types.CallToolRequest](
            types.CallToolRequest(
                params=types.CallToolRequestParams(
                    name="search_tools",
                    arguments={"query": "document", "limit": 3},
                )
            )
        )
        return result.root.structuredContent

    payload = asyncio.run(run_search())

    assert payload["ok"] is True
    assert payload["results"][0]["name"] == "files_search_files"


def test_search_tools_prefers_exact_domain_primitive() -> None:
    mcp = FastMCP("Test")

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True), structured_output=True)
    def mail_list_mailboxes() -> dict[str, bool]:
        return {"ok": True}

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True), structured_output=True)
    def apple_suggest_mailboxes() -> dict[str, bool]:
        return {"ok": True}

    @mcp.tool(structured_output=True)
    def apple_preview_follow_up_from_mail() -> dict[str, bool]:
        return {"ok": True}

    install_search_first_discovery(mcp, server_name="Test", domain="apple")

    async def run_search() -> dict[str, object]:
        result = await mcp._mcp_server.request_handlers[types.CallToolRequest](
            types.CallToolRequest(
                params=types.CallToolRequestParams(
                    name="search_tools",
                    arguments={"query": "email mailbox", "limit": 3},
                )
            )
        )
        return result.root.structuredContent

    payload = asyncio.run(run_search())

    assert payload["ok"] is True
    assert payload["results"][0]["name"] == "mail_list_mailboxes"


def test_generate_python_wrappers_uses_namespaced_root(tmp_path: Path) -> None:
    mcp = FastMCP("Test")

    @mcp.tool(structured_output=True)
    def calendar_list_events(start_iso: str, end_iso: str) -> dict[str, object]:
        return {"ok": True, "start": start_iso, "end": end_iso}

    discovery = install_search_first_discovery(mcp, server_name="Test", domain="calendar")

    asyncio.run(discovery.generate_python_wrappers(tmp_path))

    root_init = tmp_path / "apple_mcp_wrappers" / "__init__.py"
    wrapper_path = tmp_path / "apple_mcp_wrappers" / "calendar" / "calendar_list_events.py"
    client_path = tmp_path / "apple_mcp_wrappers" / "calendar" / "client.py"

    assert root_init.exists()
    assert wrapper_path.exists()
    assert client_path.exists()
    assert not (tmp_path / "calendar").exists()
    assert "call_tool_json" in wrapper_path.read_text(encoding="utf-8")
    assert "def _coerce_tool_result" in client_path.read_text(encoding="utf-8")
