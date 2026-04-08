from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def files_list_prompts(
    client: MCPToolCaller
) -> Any:
    """Files List Prompts

    Fallback prompt discovery tool for tool-only MCP clients.

    Example:
        await files_list_prompts(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "files_list_prompts", payload)
