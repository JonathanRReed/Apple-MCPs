from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_create_note_with_defaults(
    client: MCPToolCaller,
    title: str,
    body_text: str | None = None,
    body_html: str | None = None,
    folder_id: str | None = None,
    tags: list[Any] | None = None
) -> Any:
    """Apple Create Note With Defaults

    Create a note using the configured default notes folder when folder_id is omitted.

    Example:
        await apple_create_note_with_defaults(client, title='example_title', body_text='example_body_text')
    """
    arguments = {
        "title": title,
        "body_text": body_text,
        "body_html": body_html,
        "folder_id": folder_id,
        "tags": tags,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_create_note_with_defaults", payload)
