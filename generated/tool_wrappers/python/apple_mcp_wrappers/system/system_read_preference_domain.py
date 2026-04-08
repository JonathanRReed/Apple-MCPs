from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def system_read_preference_domain(
    client: MCPToolCaller,
    domain: str,
    current_host: bool | None = None
) -> Any:
    """Read Preference Domain

    Read a macOS preference domain through defaults export for a production-safe, structured settings view.

    Example:
        await system_read_preference_domain(client, domain='example_domain', current_host=False)
    """
    arguments = {
        "domain": domain,
        "current_host": current_host,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "system_read_preference_domain", payload)
