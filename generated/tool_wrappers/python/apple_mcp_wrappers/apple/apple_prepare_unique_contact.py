from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_prepare_unique_contact(
    client: MCPToolCaller,
    query: str
) -> Any:
    """Apple Prepare Unique Contact

    Resolve a contact for a person-targeted workflow, but stop and return duplicate groups if likely duplicate records need cleanup first.

    Example:
        await apple_prepare_unique_contact(client, query='find apple')
    """
    arguments = {
        "query": query,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_prepare_unique_contact", payload)
