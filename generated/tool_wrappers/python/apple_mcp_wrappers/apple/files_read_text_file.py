from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def files_read_text_file(
    client: MCPToolCaller,
    path: str,
    max_bytes: int | None = None
) -> Any:
    """Files Read Text File

    Delegated Apple domain tool 'files_read_text_file' exposed through Apple-Tools-MCP.

    Example:
        await files_read_text_file(client, path='/path/to/item', max_bytes=1)
    """
    arguments = {
        "path": path,
        "max_bytes": max_bytes,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "files_read_text_file", payload)
