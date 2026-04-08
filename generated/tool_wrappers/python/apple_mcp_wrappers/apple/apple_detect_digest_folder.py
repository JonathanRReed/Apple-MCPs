from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_detect_digest_folder(
    client: MCPToolCaller
) -> Any:
    """Apple Detect Digest Folder

    Detect the preferred Notes folder for daily and weekly digests, and persist it if found.

    Example:
        await apple_detect_digest_folder(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_detect_digest_folder", payload)
