from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def notes_list_notes(
    client: MCPToolCaller,
    account_name: str | None = None,
    folder_id: str | None = None,
    limit: int | None = None,
    offset: int | None = None
) -> Any:
    """List Notes

    List notes, optionally scoped to a folder or account.

    Example:
        await notes_list_notes(client, account_name='example_account_name', folder_id='example_folder_id')
    """
    arguments = {
        "account_name": account_name,
        "folder_id": folder_id,
        "limit": limit,
        "offset": offset,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "notes_list_notes", payload)
