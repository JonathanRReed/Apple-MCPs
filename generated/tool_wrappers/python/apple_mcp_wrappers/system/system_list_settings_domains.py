from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def system_list_settings_domains(
    client: MCPToolCaller
) -> Any:
    """List Settings Domains

    List the common macOS preference domains exposed by Apple System MCP.

    Example:
        await system_list_settings_domains(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "system_list_settings_domains", payload)
