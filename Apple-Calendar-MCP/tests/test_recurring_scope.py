"""Issue #79: writes to a repeating event must say which occurrences they cover.

These run the tools through an in-process MCP client, so the scope question is
asked over the real protocol: the 2026-07-28 input-required round trip and the
older mid-call elicitation request.
"""

import asyncio
from typing import Any

import pytest
from mcp import Client
from mcp.types import ElicitRequestParams, ElicitResult

from apple_calendar_mcp import tools
from apple_calendar_mcp.calendar_bridge import CalendarBridgeError, EventDeletion
from apple_calendar_mcp.models import EventDetail, RecurrenceInfo

SERIES_START = "2026-11-03T16:00:00Z"
PICKED = "2026-11-17T16:00:00Z"


class SeriesBridge:
    """A weekly 'Standup' series, one edited occurrence of it, and a one-off event.

    Mirrors the native helper: an unscoped write to anything in a series is refused.
    """

    def __init__(self) -> None:
        self.deletes: list[tuple[str, str | None, str | None]] = []
        self.updates: list[dict[str, Any]] = []

    def get_event(self, event_id: str) -> EventDetail:
        in_series = event_id in {"series-1", "detached-1"}
        return EventDetail(
            event_id=event_id,
            title="Standup" if in_series else "Dentist",
            calendar_id="calendar-1",
            calendar_name="Work",
            start=PICKED if event_id == "detached-1" else SERIES_START,
            end=SERIES_START,
            all_day=False,
            recurring=in_series,
            recurrence_rule=RecurrenceInfo(frequency="weekly", interval=1, end_date=None) if event_id == "series-1" else None,
        )

    def _require_scope(self, event_id: str, scope: str | None, verb: str) -> None:
        if event_id != "single-1" and scope is None:
            raise CalendarBridgeError(
                "RECURRING_EVENT_SCOPE_REQUIRED",
                f"'Standup' repeats, so nothing was {verb}.",
                "Ask the user which occurrences they mean, then call again with scope.",
            )

    def delete_event(self, event_id: str, *, scope: str | None = None, occurrence_start_iso: str | None = None) -> EventDeletion:
        self._require_scope(event_id, scope, "deleted")
        self.deletes.append((event_id, scope, occurrence_start_iso))
        return EventDeletion(True, scope, occurrence_start_iso)

    def update_event(self, event_id: str, **fields: Any) -> EventDetail:
        self._require_scope(event_id, fields.get("scope"), "updated")
        self.updates.append({"event_id": event_id, **fields})
        return self.get_event(event_id)


@pytest.fixture
def bridge(monkeypatch: pytest.MonkeyPatch) -> SeriesBridge:
    monkeypatch.setenv("APPLE_CALENDAR_MCP_SAFETY_MODE", "safe_manage")
    fake = SeriesBridge()
    monkeypatch.setattr(tools, "_bridge", lambda: fake)
    return fake


def _answering(action: str, content: dict[str, Any] | None = None, asked: list[str] | None = None):
    async def callback(context: Any, params: ElicitRequestParams) -> ElicitResult:
        if asked is not None:
            asked.append(params.message)
        return ElicitResult(action=action, content=content)  # type: ignore[arg-type]

    return callback


def _call(tool: str, arguments: dict[str, Any], *, mode: str = "auto", callback: Any = None) -> dict[str, Any]:
    async def run() -> dict[str, Any]:
        async with Client(tools.mcp, mode=mode, elicitation_callback=callback) as client:
            result = await client.call_tool(tool, arguments)
        assert isinstance(result.structured_content, dict)
        # Tools returning a response-or-error union wrap it under "result".
        return result.structured_content["result"]

    return asyncio.run(run())


@pytest.mark.parametrize("mode", ["auto", "legacy"])
def test_user_picks_one_occurrence_when_the_client_can_ask(bridge: SeriesBridge, mode: str) -> None:
    asked: list[str] = []
    result = _call(
        "calendar_delete_event",
        {"event_id": "series-1", "occurrence_start_iso": PICKED},
        mode=mode,
        callback=_answering("accept", {"scope": "occurrence"}, asked),
    )

    assert result["ok"] is True
    assert result["scope"] == "occurrence"
    assert bridge.deletes == [("series-1", "occurrence", PICKED)]
    assert len(asked) == 1
    assert "'Standup' repeats" in asked[0]
    assert "Which events should be deleted?" in asked[0]


@pytest.mark.parametrize("mode", ["auto", "legacy"])
def test_declining_the_question_changes_nothing(bridge: SeriesBridge, mode: str) -> None:
    result = _call(
        "calendar_delete_event",
        {"event_id": "series-1", "occurrence_start_iso": PICKED},
        mode=mode,
        callback=_answering("decline"),
    )

    assert result["ok"] is False
    assert result["error"]["error_code"] == "CANCELLED_BY_USER"
    assert bridge.deletes == []


def test_without_form_support_the_write_is_refused_with_guidance(bridge: SeriesBridge) -> None:
    result = _call("calendar_delete_event", {"event_id": "series-1", "occurrence_start_iso": PICKED})

    assert result["ok"] is False
    assert result["error"]["error_code"] == "RECURRING_EVENT_SCOPE_REQUIRED"
    assert "nothing was deleted" in result["error"]["message"]
    assert bridge.deletes == []


def test_an_explicit_scope_is_used_without_asking(bridge: SeriesBridge) -> None:
    asked: list[str] = []
    result = _call(
        "calendar_delete_event",
        {"event_id": "series-1", "scope": "series"},
        callback=_answering("accept", {"scope": "occurrence"}, asked),
    )

    assert result["ok"] is True
    assert asked == []
    assert bridge.deletes == [("series-1", "series", None)]


def test_events_that_do_not_repeat_are_never_asked_about(bridge: SeriesBridge) -> None:
    asked: list[str] = []
    result = _call("calendar_delete_event", {"event_id": "single-1"}, callback=_answering("accept", {"scope": "series"}, asked))

    assert result["ok"] is True
    assert asked == []
    assert bridge.deletes == [("single-1", None, None)]


def test_series_without_a_picked_occurrence_is_not_asked_about(bridge: SeriesBridge) -> None:
    # "Only this occurrence" would be ambiguous, so the agent is told to pick one first.
    asked: list[str] = []
    result = _call("calendar_delete_event", {"event_id": "series-1"}, callback=_answering("accept", {"scope": "occurrence"}, asked))

    assert asked == []
    assert result["error"]["error_code"] == "RECURRING_EVENT_SCOPE_REQUIRED"


def test_an_edited_occurrence_is_asked_about_by_its_own_id(bridge: SeriesBridge) -> None:
    asked: list[str] = []
    result = _call("calendar_delete_event", {"event_id": "detached-1"}, callback=_answering("accept", {"scope": "series"}, asked))

    assert result["ok"] is True
    assert len(asked) == 1
    assert bridge.deletes == [("detached-1", "series", None)]


def test_update_asks_and_passes_the_chosen_scope(bridge: SeriesBridge) -> None:
    asked: list[str] = []
    result = _call(
        "calendar_update_event",
        {"event_id": "series-1", "occurrence_start_iso": PICKED, "title": "Sync"},
        callback=_answering("accept", {"scope": "following"}, asked),
    )

    assert result["ok"] is True
    assert "Which events should be changed?" in asked[0]
    assert bridge.updates[0]["scope"] == "following"
    assert bridge.updates[0]["occurrence_start_iso"] == PICKED


def test_the_choice_is_not_an_input_the_model_can_fill() -> None:
    for name in ("calendar_delete_event", "calendar_update_event"):
        tool = tools.mcp._tool_manager.get_tool(name)
        assert tool is not None
        properties = tool.parameters["properties"]
        assert "choice" not in properties
        assert properties["scope"]["anyOf"][0]["enum"] == ["occurrence", "following", "series"]
        assert "occurrence_start_iso" in properties
