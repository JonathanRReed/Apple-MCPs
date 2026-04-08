from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def maps_list_prompts(
    client: MCPToolCaller
) -> Any:
    """Maps List Prompts

    Fallback prompt discovery tool for tool-only MCP clients.

    Example:
        await maps_list_prompts(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "maps_list_prompts", payload)
