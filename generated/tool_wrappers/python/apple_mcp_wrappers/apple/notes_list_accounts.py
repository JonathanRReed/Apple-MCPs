from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def notes_list_accounts(
    client: MCPToolCaller
) -> Any:
    """Notes List Accounts

    Delegated Apple domain tool 'notes_list_accounts' exposed through Apple-Tools-MCP.

    Example:
        await notes_list_accounts(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "notes_list_accounts", payload)
