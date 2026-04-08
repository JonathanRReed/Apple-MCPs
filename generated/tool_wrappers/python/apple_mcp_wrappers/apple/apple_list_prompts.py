from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_list_prompts(
    client: MCPToolCaller
) -> Any:
    """Apple List Prompts

    Fallback prompt discovery tool for clients that only support tools.

    Example:
        await apple_list_prompts(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_list_prompts", payload)
