import asyncio

import pytest

from apple_agent_mcp.tools import mcp as unified
from apple_calendar_mcp.tools import mcp as calendar


@pytest.mark.parametrize("server", [calendar, unified], ids=["standalone", "unified"])
def test_calendar_alarm_search_and_complete_tool_schema(server):
    async def check():
        result = await server.call_tool("search_tools", {"query": "calendar alarms", "limit": 10})
        names = {entry["name"] for entry in result.structured_content["results"]}
        assert {"calendar_create_event", "calendar_update_event"} <= names
        for name in ("calendar_create_event", "calendar_update_event"):
            result = await server.call_tool("get_tool_info", {"name": name})
            payload = result.structured_content
            assert payload["ok"]
            assert "alarms" in payload["input_schema"]["properties"]
            assert "alarms" in payload["description"].lower()
    asyncio.run(check())
