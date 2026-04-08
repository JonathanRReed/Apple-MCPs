from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_get_prompt(
    client: MCPToolCaller,
    name: str,
    arguments_json: str | None = None
) -> Any:
    """Apple Get Prompt

    Fallback prompt rendering tool for clients that only support tools.

    Example:
        await apple_get_prompt(client, name='example_name', arguments_json='example_arguments_json')
    """
    arguments = {
        "name": name,
        "arguments_json": arguments_json,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_get_prompt", payload)
