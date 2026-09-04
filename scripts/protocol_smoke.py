#!/usr/bin/env python3
"""Check every installed server over current and legacy stdio without reading app data."""

from __future__ import annotations

import asyncio
import json
import shutil
from importlib.metadata import version

from jsonschema import Draft202012Validator
from mcp import Client, StdioServerParameters

SERVERS = (
    "apple-tools-mcp", "apple-calendar-mcp", "apple-contacts-mcp",
    "apple-files-mcp", "apple-mail-mcp", "apple-maps-mcp",
    "apple-messages-mcp", "apple-notes-mcp", "apple-reminders-mcp",
    "apple-shortcuts-mcp", "apple-system-mcp",
)


async def check_server(binary: str, mode: str, parameters: StdioServerParameters | None = None, *, timeout: float = 30) -> None:
    if parameters is None:
        command = shutil.which(binary)
        if command is None:
            raise RuntimeError(f"Missing installed entry point: {binary}")
        parameters = StdioServerParameters(command=command)
    async with Client(parameters, mode=mode, read_timeout_seconds=timeout) as client:
        result = await client.list_tools()
        names = [tool.name for tool in result.tools]
        assert names and len(names) == len(set(names)), (binary, "empty or duplicate tools")
        assert {"search_tools", "get_tool_info"} <= set(names), binary
        for tool in result.tools:
            Draft202012Validator.check_schema(tool.input_schema)
            if tool.output_schema is not None:
                Draft202012Validator.check_schema(tool.output_schema)
        called = await client.call_tool("search_tools", {"query": "health", "limit": 1})
        if mode == "auto":
            assert client.protocol_version == "2026-07-28", (binary, client.protocol_version)
        else:
            assert client.protocol_version < "2026-07-28", (binary, client.protocol_version)
        assert client.server_info is not None and client.server_info.version == version("apple-mcp-common"), binary
        assert not called.is_error, (binary, called)
        data = called.structured_content
        assert isinstance(data, dict) and data["ok"] is True and data["count"] > 0, (binary, data)
        schema = next(tool.output_schema for tool in result.tools if tool.name == "search_tools")
        assert schema is not None, binary
        Draft202012Validator(schema).validate(data)
        text = next(item.text for item in called.content if item.type == "text")
        assert json.loads(text) == data, (binary, "text and structured output differ")
        unknown = await client.call_tool("release_check_missing_tool", {})
        assert unknown.is_error, (binary, "unknown tool did not return a tool error")
        print(f"PASS {binary} mode={mode}: {len(names)} tools, schemas, call, structured output, error", flush=True)


async def main() -> None:
    for binary in SERVERS:
        for mode in ("auto", "legacy"):
            async with asyncio.timeout(90):
                await check_server(binary, mode)


if __name__ == "__main__":
    asyncio.run(main())
