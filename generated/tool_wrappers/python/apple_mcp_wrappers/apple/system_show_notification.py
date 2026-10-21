from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def system_show_notification(
    client: MCPToolCaller,
    title: str,
    body: str,
    subtitle: str | None = None
) -> Any:
    """Show Notification

    Display a local macOS notification.

    Example:
        await system_show_notification(client, title='example_title', body='example_body')
    """
    arguments = {
        "title": title,
        "body": body,
        "subtitle": subtitle,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "system_show_notification", payload)
