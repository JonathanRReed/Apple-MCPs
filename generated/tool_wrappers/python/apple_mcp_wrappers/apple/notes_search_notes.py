from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def notes_search_notes(
    client: MCPToolCaller,
    query: str,
    account_name: str | None = None,
    folder_id: str | None = None,
    limit: int | None = None,
    offset: int | None = None
) -> Any:
    """Notes Search Notes

    Delegated Apple domain tool 'notes_search_notes' exposed through Apple-Tools-MCP.

    Example:
        await notes_search_notes(client, query='find apple', account_name='example_account_name')
    """
    arguments = {
        "query": query,
        "account_name": account_name,
        "folder_id": folder_id,
        "limit": limit,
        "offset": offset,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "notes_search_notes", payload)
