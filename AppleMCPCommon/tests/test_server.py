from __future__ import annotations

import asyncio
import json
from typing import Literal

from mcp import Client
from mcp.types import CallToolResult, TextContent
from pydantic import BaseModel

from apple_mcp_common.server import AppleMCPServer, flag_failed_tool_result


class Failure(BaseModel):
    ok: Literal[False] = False
    message: str


class Success(BaseModel):
    ok: Literal[True] = True
    value: int


def _server() -> AppleMCPServer:
    server = AppleMCPServer("test")

    @server.tool(structured_output=True)
    def union_tool(fail: bool = False) -> Success | Failure:
        return Failure(message="nope") if fail else Success(value=1)

    @server.tool(structured_output=True)
    def model_tool(fail: bool = False) -> Failure:
        return Failure(message="plain")

    @server.tool(structured_output=True)
    def dict_tool(fail: bool = False) -> dict[str, object]:
        return {"ok": not fail, "nested": {"ok": False}}

    return server


def test_flag_failed_tool_result_keeps_content() -> None:
    content = [TextContent(type="text", text='{"ok": false}')]
    wrapped = CallToolResult(content=content, structured_content={"result": {"ok": False}})
    flagged = flag_failed_tool_result(wrapped, wrapped=True)
    assert flagged.is_error is True
    assert flagged.structured_content == {"result": {"ok": False}}
    assert flagged.content == content
    # A top-level "result" key is only unwrapped for SDK-wrapped outputs.
    assert flag_failed_tool_result(wrapped, wrapped=False).is_error is False
    assert flag_failed_tool_result(CallToolResult(content=[], structured_content={"ok": True}), wrapped=False).is_error is False
    assert flag_failed_tool_result(CallToolResult(content=[]), wrapped=False).is_error is False


def test_failed_payloads_set_is_error_on_the_wire() -> None:
    async def scenario() -> None:
        async with Client(_server()) as client:
            ok = await client.call_tool("union_tool", {})
            assert ok.is_error is False
            assert ok.structured_content == {"result": {"ok": True, "value": 1}}

            failed = await client.call_tool("union_tool", {"fail": True})
            assert failed.is_error is True
            assert failed.structured_content == {"result": {"ok": False, "message": "nope"}}
            text = next(item.text for item in failed.content if isinstance(item, TextContent))
            assert json.loads(text) == {"ok": False, "message": "nope"}

            plain = await client.call_tool("model_tool", {})
            assert plain.is_error is True
            assert plain.structured_content == {"ok": False, "message": "plain"}

            # Only the top-level ok flag counts; nested ok=false sub-results are data.
            assert (await client.call_tool("dict_tool", {})).is_error is False
            assert (await client.call_tool("dict_tool", {"fail": True})).is_error is True

    asyncio.run(scenario())
