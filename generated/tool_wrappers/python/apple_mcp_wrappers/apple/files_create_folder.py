from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def files_create_folder(
    client: MCPToolCaller,
    path: str
) -> Any:
    """Create Folder

    Create a folder inside the allowed roots.

    Example:
        await files_create_folder(client, path='/path/to/item')
    """
    arguments = {
        "path": path,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "files_create_folder", payload)
