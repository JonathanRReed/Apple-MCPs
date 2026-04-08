from __future__ import annotations

import json

from typing import Any, Protocol


class MCPToolCaller(Protocol):
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...


def _coerce_tool_result(result: Any) -> Any:
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return structured
    content = getattr(result, "content", None) or []
    chunks: list[str] = []
    for item in content:
        text = getattr(item, "text", None)
        if text:
            chunks.append(text)
    if not chunks:
        return result
    text_payload = "".join(chunks)
    try:
        return json.loads(text_payload)
    except json.JSONDecodeError:
        return text_payload


async def call_tool_json(client: MCPToolCaller, name: str, arguments: dict[str, Any]) -> Any:
    result = await client.call_tool(name, arguments)
    return _coerce_tool_result(result)
