from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def contacts_health(
    client: MCPToolCaller
) -> Any:
    """Contacts Health

    Delegated Apple domain tool 'contacts_health' exposed through Apple-Tools-MCP.

    Example:
        await contacts_health(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "contacts_health", payload)
