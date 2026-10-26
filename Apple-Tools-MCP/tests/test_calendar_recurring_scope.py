import asyncio
from typing import Any

import pytest
from mcp import Client
from mcp.types import ElicitRequestParams, ElicitResult

import apple_calendar_mcp.tools as calendar_tools
from apple_agent_mcp.tools import mcp as unified
from apple_calendar_mcp.calendar_bridge import EventDeletion
from apple_calendar_mcp.models import EventDetail


class SeriesBridge:
    def __init__(self) -> None:
        self.deletes: list[tuple[str, str | None, str | None]] = []

    def get_event(self, event_id: str) -> EventDetail:
        return EventDetail(
            event_id=event_id, title="Standup", calendar_id="calendar-1", calendar_name="Work",
            start="2026-11-03T16:00:00Z", end="2026-11-03T16:30:00Z", all_day=False, recurring=True,
            recurrence_rule={"frequency": "weekly", "interval": 1, "end_date": None},
        )

    def delete_event(self, event_id: str, *, scope: str | None = None, occurrence_start_iso: str | None = None) -> EventDeletion:
        self.deletes.append((event_id, scope, occurrence_start_iso))
        return EventDeletion(True, scope, occurrence_start_iso)


def test_unified_server_asks_which_occurrences_to_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPLE_CALENDAR_MCP_SAFETY_MODE", "safe_manage")
    bridge = SeriesBridge()
    monkeypatch.setattr(calendar_tools, "_bridge", lambda: bridge)
    asked: list[str] = []

    async def answer(context: Any, params: ElicitRequestParams) -> ElicitResult:
        asked.append(params.message)
        return ElicitResult(action="accept", content={"scope": "following"})

    async def run() -> tuple[dict[str, Any], dict[str, Any]]:
        info = await unified.call_tool("get_tool_info", {"name": "calendar_delete_event"})
        async with Client(unified, elicitation_callback=answer) as client:
            result = await client.call_tool(
                "calendar_delete_event", {"event_id": "series-1", "occurrence_start_iso": "2026-11-17T16:00:00Z"},
            )
        return info.structured_content, result.structured_content["result"]

    info, result = asyncio.run(run())

    properties = info["input_schema"]["properties"]
    assert "choice" not in properties
    assert {"scope", "occurrence_start_iso"} <= set(properties)
    assert "RECURRING_EVENT_SCOPE_REQUIRED" in info["description"]
    assert result["ok"] is True
    assert len(asked) == 1
    assert bridge.deletes == [("series-1", "following", "2026-11-17T16:00:00Z")]
