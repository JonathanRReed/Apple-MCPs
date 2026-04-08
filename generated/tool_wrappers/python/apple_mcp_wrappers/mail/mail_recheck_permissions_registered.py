from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def mail_recheck_permissions_registered(
    client: MCPToolCaller
) -> Any:
    """Mail Recheck Permissions

    Recheck Mail access after the user changes macOS permissions, and notify the client that Mail resources changed.

    Example:
        await mail_recheck_permissions_registered(client)
    """
    arguments = {

    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "mail_recheck_permissions_registered", payload)
