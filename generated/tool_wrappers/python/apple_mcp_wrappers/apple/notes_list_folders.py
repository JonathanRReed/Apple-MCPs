from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def notes_list_folders(
    client: MCPToolCaller,
    account_name: str | None = None,
    limit: int | None = None,
    offset: int | None = None
) -> Any:
    """Notes List Folders

    Delegated Apple domain tool 'notes_list_folders' exposed through Apple-Tools-MCP.

    Example:
        await notes_list_folders(client, account_name='example_account_name', limit=1)
    """
    arguments = {
        "account_name": account_name,
        "limit": limit,
        "offset": offset,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "notes_list_folders", payload)
