from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def files_recent_files(
    client: MCPToolCaller,
    limit: int | None = None
) -> Any:
    """Files Recent Files

    Delegated Apple domain tool 'files_recent_files' exposed through Apple-Tools-MCP.

    Example:
        await files_recent_files(client, limit=1)
    """
    arguments = {
        "limit": limit,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "files_recent_files", payload)
