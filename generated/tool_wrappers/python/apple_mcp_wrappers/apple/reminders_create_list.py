from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def reminders_create_list(
    client: MCPToolCaller,
    title: str
) -> Any:
    """Reminders Create List

    Delegated Apple domain tool 'reminders_create_list' exposed through Apple-Tools-MCP.

    Example:
        await reminders_create_list(client, title='example_title')
    """
    arguments = {
        "title": title,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "reminders_create_list", payload)
