from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def files_list_allowed_roots(
    client: MCPToolCaller
) -> Any:
    """List Allowed Roots

    List the file system roots the server may access.

    Example:
        await files_list_allowed_roots(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "files_list_allowed_roots", payload)
