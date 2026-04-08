from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_generate_weekly_briefing(
    client: MCPToolCaller,
    days: int | None = None,
    mail_query: str | None = None,
    mail_limit: int | None = None
) -> Any:
    """Apple Generate Weekly Briefing

    Generate a weekly Apple briefing. Supports task-augmented execution for longer runs.

    Example:
        await apple_generate_weekly_briefing(client, days=1, mail_query='find apple')
    """
    arguments = {
        "days": days,
        "mail_query": mail_query,
        "mail_limit": mail_limit,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_generate_weekly_briefing", payload)
