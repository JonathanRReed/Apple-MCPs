from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_preview_create_note_with_defaults(
    client: MCPToolCaller,
    title: str,
    body_text: str | None = None,
    body_html: str | None = None,
    folder_id: str | None = None,
    tags: list[Any] | None = None
) -> Any:
    """Apple Preview Create Note With Defaults

    Preview how Apple-Tools will create a note with the configured default notes folder.

    Example:
        await apple_preview_create_note_with_defaults(client, title='example_title', body_text='example_body_text')
    """
    arguments = {
        "title": title,
        "body_text": body_text,
        "body_html": body_html,
        "folder_id": folder_id,
        "tags": tags,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_preview_create_note_with_defaults", payload)
