from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_route_or_run_shortcut(
    client: MCPToolCaller,
    request: str,
    shortcut_name_or_identifier: str | None = None,
    input_text: str | None = None,
    input_paths: list[Any] | None = None,
    dry_run: bool | None = None
) -> Any:
    """Apple Route Or Run Shortcut

    Use Apple Shortcuts as the explicit bridge when native Apple MCP coverage is insufficient or when the user names a shortcut directly.

    Example:
        await apple_route_or_run_shortcut(client, request='example_request', shortcut_name_or_identifier='example_shortcut_name_or_identifier')
    """
    arguments = {
        "request": request,
        "shortcut_name_or_identifier": shortcut_name_or_identifier,
        "input_text": input_text,
        "input_paths": input_paths,
        "dry_run": dry_run,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_route_or_run_shortcut", payload)
