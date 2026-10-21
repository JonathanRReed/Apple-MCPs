from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.types import CallToolResult, InputRequiredResult


def flag_failed_tool_result(result: CallToolResult, *, wrapped: bool) -> CallToolResult:
    """Set ``isError`` on a tool result whose payload reports ``ok: false``.

    The Apple servers return failures as structured payloads such as
    ``ErrorResponse`` (``{"ok": false, "error": {...}}``). Spec 2025-06-18 and
    later say tool execution failures belong in a result with ``isError: true``,
    so this keeps the structured and text content exactly as produced and only
    flips the flag. ``wrapped`` is true when the SDK nested the payload under
    ``{"result": ...}`` (union and non-object return types).
    """
    if result.is_error:
        return result
    payload: Any = result.structured_content
    if wrapped and isinstance(payload, dict):
        payload = payload.get("result")
    if isinstance(payload, dict) and payload.get("ok") is False:
        return result.model_copy(update={"is_error": True})
    return result


class AppleMCPServer(MCPServer[Any]):
    """MCPServer whose ``ok: false`` tool results are reported with ``isError: true``."""

    async def call_tool(
        self, name: str, arguments: dict[str, Any], context: Context[Any, Any] | None = None
    ) -> CallToolResult | InputRequiredResult:
        result = await super().call_tool(name, arguments, context)
        if not isinstance(result, CallToolResult):
            return result
        tool = self._tool_manager.get_tool(name)
        wrapped = tool is not None and tool.fn_metadata.wrap_output
        return flag_failed_tool_result(result, wrapped=wrapped)
