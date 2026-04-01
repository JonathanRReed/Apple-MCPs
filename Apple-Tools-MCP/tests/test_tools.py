import json
import asyncio

from apple_agent_mcp import tools
from apple_contacts_mcp.models import ContactDetail, ContactMethod, ResolvedRecipientResponse


def test_registered_tool_names_cover_core_domains() -> None:
    assert "apple_permission_guide" in tools.REGISTERED_TOOL_NAMES
    assert "apple_recheck_permissions" in tools.REGISTERED_TOOL_NAMES
    assert "apple_send_message_interactive" in tools.REGISTERED_TOOL_NAMES
    assert "apple_create_event_interactive" in tools.REGISTERED_TOOL_NAMES
    assert "mail_list_mailboxes" in tools.REGISTERED_TOOL_NAMES
    assert "calendar_list_events" in tools.REGISTERED_TOOL_NAMES
    assert "reminders_list_reminders" in tools.REGISTERED_TOOL_NAMES
    assert "messages_send_message" in tools.REGISTERED_TOOL_NAMES
    assert "contacts_search_contacts" in tools.REGISTERED_TOOL_NAMES
    assert "shortcuts_run_shortcut" in tools.REGISTERED_TOOL_NAMES


def test_aio_prompt_list_includes_routing_and_contacts_prompts() -> None:
    async def load_prompt_names() -> list[str]:
        prompt_list = await tools.mcp.list_prompts()
        return [prompt.name for prompt in prompt_list]

    prompt_names = asyncio.run(load_prompt_names())

    assert "apple_route_request" in prompt_names
    assert "contacts_prepare_message_recipient" in prompt_names


def test_apple_health_aggregates_domains(monkeypatch) -> None:
    monkeypatch.setattr(tools, "mail_health", lambda: {"ok": True, "server_name": "Mail"})
    monkeypatch.setattr(tools, "calendar_health", lambda: {"ok": True, "server_name": "Calendar"})
    monkeypatch.setattr(tools, "reminders_health", lambda: {"ok": True, "server_name": "Reminders"})
    monkeypatch.setattr(tools, "messages_health", lambda: {"ok": True, "server_name": "Messages"})
    monkeypatch.setattr(tools, "contacts_health", lambda: {"ok": True, "server_name": "Contacts"})
    monkeypatch.setattr(tools, "notes_health", lambda: {"ok": True, "server_name": "Notes"})
    monkeypatch.setattr(tools, "shortcuts_health", lambda: {"ok": True, "server_name": "Shortcuts"})

    result = tools.apple_health()

    assert result.ok is True
    assert result.domains["contacts"]["server_name"] == "Contacts"
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


def test_apple_send_message_interactive_resolves_contact_name(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_message_recipient(query: str, channel: str = "phone"):
        assert query == "Alice Doe"
        assert channel == "any"
        return ResolvedRecipientResponse(
            contact=ContactDetail(
                contact_id="contact-1",
                name="Alice Doe",
                first_name="Alice",
                last_name="Doe",
                organization="",
                phone_count=1,
                email_count=0,
                phones=[ContactMethod(label="mobile", value="+15551234567")],
                emails=[],
                note="",
            ),
            recipient_kind="phone",
            recipient_label="mobile",
            recipient_value="+15551234567",
        )

    def fake_send_message(recipient: str, text: str, service_name: str | None = None):
        captured["recipient"] = recipient
        captured["text"] = text
        captured["service_name"] = service_name
        return {"ok": True, "sent": True, "recipient": recipient, "text": text, "service_name": service_name}

    monkeypatch.setattr(tools, "contacts_resolve_message_recipient", fake_resolve_message_recipient)
    monkeypatch.setattr(tools, "messages_send_message", fake_send_message)

    result = asyncio.run(tools.apple_send_message_interactive(recipient="Alice Doe", text="hi"))

    assert result["ok"] is True
    assert captured["recipient"] == "+15551234567"


def test_apple_send_message_interactive_falls_back_to_contact_email(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_message_recipient(query: str, channel: str = "phone"):
        assert query == "Alice Doe"
        assert channel == "any"
        return ResolvedRecipientResponse(
            contact=ContactDetail(
                contact_id="contact-1",
                name="Alice Doe",
                first_name="Alice",
                last_name="Doe",
                organization="",
                phone_count=0,
                email_count=1,
                phones=[],
                emails=[ContactMethod(label="iMessage", value="alice@example.com")],
                note="",
            ),
            recipient_kind="email",
            recipient_label="iMessage",
            recipient_value="alice@example.com",
        )

    def fake_send_message(recipient: str, text: str, service_name: str | None = None):
        captured["recipient"] = recipient
        captured["text"] = text
        captured["service_name"] = service_name
        return {"ok": True, "sent": True, "recipient": recipient, "text": text, "service_name": service_name}

    monkeypatch.setattr(tools, "contacts_resolve_message_recipient", fake_resolve_message_recipient)
    monkeypatch.setattr(tools, "messages_send_message", fake_send_message)

    result = asyncio.run(tools.apple_send_message_interactive(recipient="Alice Doe", text="hi"))

    assert result["ok"] is True
    assert captured["recipient"] == "alice@example.com"
