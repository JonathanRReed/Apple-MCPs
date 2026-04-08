from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def calendar_list_prompts(
    client: MCPToolCaller
) -> Any:
    """Calendar List Prompts

    Fallback prompt discovery tool for tool-only MCP clients.

    Example:
        await calendar_list_prompts(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "calendar_list_prompts", payload)
