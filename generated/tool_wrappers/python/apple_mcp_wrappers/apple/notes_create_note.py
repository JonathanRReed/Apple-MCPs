from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def notes_create_note(
    client: MCPToolCaller,
    title: str,
    folder_id: str,
    body_html: str | None = None,
    tags: list[Any] | None = None
) -> Any:
    """Notes Create Note

    Delegated Apple domain tool 'notes_create_note' exposed through Apple-Tools-MCP.

    Example:
        await notes_create_note(client, title='example_title', folder_id='example_folder_id')
    """
    arguments = {
        "title": title,
        "folder_id": folder_id,
        "body_html": body_html,
        "tags": tags,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "notes_create_note", payload)
