from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def files_search_files(
    client: MCPToolCaller,
    query: str,
    base_path: str | None = None,
    limit: int | None = None
) -> Any:
    """Files Search Files

    Delegated Apple domain tool 'files_search_files' exposed through Apple-Tools-MCP.

    Example:
        await files_search_files(client, query='find apple', base_path='/path/to/item')
    """
    arguments = {
        "query": query,
        "base_path": base_path,
        "limit": limit,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "files_search_files", payload)
