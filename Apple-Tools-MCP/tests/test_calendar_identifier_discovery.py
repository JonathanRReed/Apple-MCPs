import asyncio

import pytest

from apple_agent_mcp.tools import mcp as unified
from apple_calendar_mcp.tools import mcp as calendar


@pytest.mark.parametrize("server", [calendar, unified], ids=["standalone", "unified"])
@pytest.mark.parametrize(
    "name",
    ["calendar_list_events", "calendar_create_event", "calendar_update_event"],
)
def test_calendar_identifier_schema_guides_discovery_without_changing_contract(server, name):
    async def check():
        result = await server.call_tool("get_tool_info", {"name": name})
        payload = result.structured_content
        assert payload["ok"]
        schema = payload["input_schema"]
        calendar_id = dict(schema["properties"]["calendar_id"])
        description = calendar_id.pop("description", "")
        assert "calendar_list_calendars" in description
        assert "name" in description
        assert "unchanged" in description
        assert "Re-list" in description
        assert "native" in description
        if name == "calendar_create_event":
            assert calendar_id == {"title": "Calendar Id", "type": "string"}
            assert "calendar_id" in schema["required"]
        else:
            assert calendar_id == {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "default": None,
                "title": "Calendar Id",
            }
            assert "calendar_id" not in schema.get("required", [])
    asyncio.run(check())


@pytest.mark.parametrize("server", [calendar, unified], ids=["standalone", "unified"])
def test_calendar_update_schema_explains_native_event_identifier_for_full_alarm_edits(server):
    async def check():
        result = await server.call_tool("get_tool_info", {"name": "calendar_update_event"})
        schema = result.structured_content["input_schema"]
        event_id = dict(schema["properties"]["event_id"])
        description = event_id.pop("description", "")
        assert "calendar_list_events" in description
        assert "native calendar_id" in description
        assert "native event_id" in description
        assert "full alarm edits" in description
        assert "applescript::" in description
        assert event_id == {"title": "Event Id", "type": "string"}
        assert "event_id" in schema["required"]
    asyncio.run(check())


@pytest.mark.parametrize("server", [calendar, unified], ids=["standalone", "unified"])
def test_calendar_search_exposes_identifier_selection_and_refresh_guidance(server):
    async def check():
        result = await server.call_tool("search_tools", {"query": "calendar", "limit": 20})
        entries = {entry["name"]: entry for entry in result.structured_content["results"]}
        listing = entries["calendar_list_calendars"]["description"]
        assert "name" in listing
        assert "calendar_id unchanged" in listing
        assert "Re-list" in listing
        for name in ("calendar_list_events", "calendar_create_event"):
            assert "calendar_list_calendars" in entries[name]["description"]
        assert "native event_id" in entries["calendar_update_event"]["description"]
    asyncio.run(check())
