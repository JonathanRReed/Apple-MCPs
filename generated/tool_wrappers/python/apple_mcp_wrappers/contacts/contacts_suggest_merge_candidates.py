from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def contacts_suggest_merge_candidates(
    client: MCPToolCaller,
    query: str | None = None
) -> Any:
    """Suggest Merge Candidates

    Return likely duplicate Apple Contacts groups that are strong candidates for cleanup review.

    Example:
        await contacts_suggest_merge_candidates(client, query='find contacts')
    """
    arguments = {
        "query": query,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "contacts_suggest_merge_candidates", payload)
