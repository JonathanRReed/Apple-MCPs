from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def shortcuts_run_shortcut(
    client: MCPToolCaller,
    shortcut_name_or_identifier: str,
    input_paths: list[Any] | None = None,
    output_path: str | None = None,
    output_type: str | None = None,
    input_text: str | None = None
) -> Any:
    """Shortcuts Run Shortcut

    Delegated Apple domain tool 'shortcuts_run_shortcut' exposed through Apple-Tools-MCP.

    Example:
        await shortcuts_run_shortcut(client, shortcut_name_or_identifier='example_shortcut_name_or_identifier', input_paths=[])
    """
    arguments = {
        "shortcut_name_or_identifier": shortcut_name_or_identifier,
        "input_paths": input_paths,
        "output_path": output_path,
        "output_type": output_type,
        "input_text": input_text,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "shortcuts_run_shortcut", payload)
