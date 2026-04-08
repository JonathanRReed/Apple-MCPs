from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_set_digest_folder(
    client: MCPToolCaller,
    folder_id: str,
    folder_name: str | None = None,
    account_name: str | None = None
) -> Any:
    """Apple Set Digest Folder

    Persist the dedicated Notes folder that Apple-Tools should use for daily and weekly digests.

    Example:
        await apple_set_digest_folder(client, folder_id='example_folder_id', folder_name='example_folder_name')
    """
    arguments = {
        "folder_id": folder_id,
        "folder_name": folder_name,
        "account_name": account_name,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_set_digest_folder", payload)
