from __future__ import annotations

from typing import Any

from .client import MCPToolCaller, call_tool_json


async def apple_undo_action(
    client: MCPToolCaller,
    action_id: str
) -> Any:
    """Apple Undo Action

    Undo a recent Apple-Tools action when the underlying standalone MCPs support a reliable reversal.

    Example:
        await apple_undo_action(client, action_id='example_action_id')
    """
    arguments = {
        "action_id": action_id,
    }
    payload = {key: value for key, value in arguments.items() if value is not None}
    return await call_tool_json(client, "apple_undo_action", payload)
