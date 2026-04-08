from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def files_move_path(
    client: MCPToolCaller,
    source: str,
    destination: str
) -> Any:
    """Move Path

    Move or rename a file or folder inside the allowed roots.

    Example:
        await files_move_path(client, source='example_source', destination='example_destination')
    """
    arguments = {
        "source": source,
        "destination": destination,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "files_move_path", payload)
