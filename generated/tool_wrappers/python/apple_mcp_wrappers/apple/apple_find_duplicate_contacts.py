from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_find_duplicate_contacts(
    client: MCPToolCaller,
    query: str | None = None,
    merge_candidates_only: bool | None = None
) -> Any:
    """Apple Find Duplicate Contacts

    Find likely duplicate contacts through Apple Contacts so assistants can disambiguate people before acting.

    Example:
        await apple_find_duplicate_contacts(client, query='find apple', merge_candidates_only=False)
    """
    arguments = {
        "query": query,
        "merge_candidates_only": merge_candidates_only,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_find_duplicate_contacts", payload)
