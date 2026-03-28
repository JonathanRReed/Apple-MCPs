import json
import asyncio

from apple_agent_mcp import tools


def test_registered_tool_names_cover_core_domains() -> None:
    assert "apple_permission_guide" in tools.REGISTERED_TOOL_NAMES
    assert "apple_recheck_permissions" in tools.REGISTERED_TOOL_NAMES
    assert "apple_send_message_interactive" in tools.REGISTERED_TOOL_NAMES
    assert "apple_create_event_interactive" in tools.REGISTERED_TOOL_NAMES
    assert "mail_list_mailboxes" in tools.REGISTERED_TOOL_NAMES
    assert "calendar_list_events" in tools.REGISTERED_TOOL_NAMES
    assert "reminders_list_reminders" in tools.REGISTERED_TOOL_NAMES
    assert "messages_send_message" in tools.REGISTERED_TOOL_NAMES
    assert "shortcuts_run_shortcut" in tools.REGISTERED_TOOL_NAMES


def test_apple_health_aggregates_domains(monkeypatch) -> None:
    monkeypatch.setattr(tools, "mail_health", lambda: {"ok": True, "server_name": "Mail"})
    monkeypatch.setattr(tools, "calendar_health", lambda: {"ok": True, "server_name": "Calendar"})
    monkeypatch.setattr(tools, "reminders_health", lambda: {"ok": True, "server_name": "Reminders"})
    monkeypatch.setattr(tools, "messages_health", lambda: {"ok": True, "server_name": "Messages"})
    monkeypatch.setattr(tools, "notes_health", lambda: {"ok": True, "server_name": "Notes"})
    monkeypatch.setattr(tools, "shortcuts_health", lambda: {"ok": True, "server_name": "Shortcuts"})

    result = tools.apple_health()

    assert result.ok is True
    assert result.domains["mail"]["server_name"] == "Mail"
    assert result.domains["shortcuts"]["server_name"] == "Shortcuts"


def test_apple_today_resource_combines_domain_payloads(monkeypatch) -> None:
    monkeypatch.setattr(tools, "calendar_events_today_resource", lambda: json.dumps({"events": [{"title": "Standup"}]}))
    monkeypatch.setattr(tools, "reminders_today_resource", lambda: json.dumps({"reminders": [{"title": "Ship"}]}))
    monkeypatch.setattr(tools, "messages_unread_resource", lambda: json.dumps({"conversations": [{"chat_id": "1"}]}))
    monkeypatch.setattr(tools, "notes_recent_resource", lambda: json.dumps({"notes": [{"title": "Prep"}]}))

    payload = json.loads(tools.apple_today_resource())

    assert payload["calendar_today"]["events"][0]["title"] == "Standup"
    assert payload["reminders_today"]["reminders"][0]["title"] == "Ship"


def test_aio_messages_get_conversation_schema_uses_integer_limit() -> None:
    async def load_schema():
        tool_list = await tools.mcp.list_tools()
        return next(tool.inputSchema for tool in tool_list if tool.name == "messages_get_conversation")

    schema = asyncio.run(load_schema())

    assert schema["properties"]["limit"]["anyOf"] == [{"type": "integer"}, {"type": "string"}]


def test_aio_messages_get_conversation_accepts_string_limit(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_get_conversation(chat_id: str, limit: int = 50, offset: int = 0):
        captured["chat_id"] = chat_id
        captured["limit"] = limit
        captured["offset"] = offset
        return {"ok": True}

    monkeypatch.setattr(tools, "_messages_get_conversation", fake_get_conversation)

    result = tools.messages_get_conversation("chat-guid-1", limit="3", offset="1")

    assert result == {"ok": True}
    assert captured == {"chat_id": "chat-guid-1", "limit": 3, "offset": 1}
