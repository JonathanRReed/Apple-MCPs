from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def files_get_icloud_status(
    client: MCPToolCaller
) -> Any:
    """Files Get Icloud Status

    Delegated Apple domain tool 'files_get_icloud_status' exposed through Apple-Tools-MCP.

    Example:
        await files_get_icloud_status(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "files_get_icloud_status", payload)
