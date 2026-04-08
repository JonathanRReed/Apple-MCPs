from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_triage_communications_task(
    client: MCPToolCaller,
    mail_query: str | None = None,
    mail_limit: int | None = None,
    conversation_limit: int | None = None
) -> Any:
    """Apple Triage Communications Task

    Generate a cross-app communications triage summary. Supports task-augmented execution.

    Example:
        await apple_triage_communications_task(client, mail_query='find apple', mail_limit=1)
    """
    arguments = {
        "mail_query": mail_query,
        "mail_limit": mail_limit,
        "conversation_limit": conversation_limit,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_triage_communications_task", payload)
