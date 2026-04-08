from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_ensure_digest_folder(
    client: MCPToolCaller,
    folder_name: str | None = None,
    account_name: str | None = None
) -> Any:
    """Apple Ensure Digest Folder

    Ensure a dedicated Notes folder exists for daily and weekly digests, creating it when necessary and persisting the preference.

    Example:
        await apple_ensure_digest_folder(client, folder_name='example_folder_name', account_name='example_account_name')
    """
    arguments = {
        "folder_name": folder_name,
        "account_name": account_name,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_ensure_digest_folder", payload)
