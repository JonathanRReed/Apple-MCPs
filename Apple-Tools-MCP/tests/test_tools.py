import json
import asyncio

from mcp import types
from mcp.server.fastmcp import FastMCP

from apple_agent_mcp.conformance import enable_conformance_mode
from apple_agent_mcp import tools
from apple_agent_mcp.config import load_settings
from apple_contacts_mcp.models import ContactDetail, ContactMethod, ResolvedRecipientResponse


def test_registered_tool_names_cover_core_domains() -> None:
    assert "apple_permission_guide" in tools.REGISTERED_TOOL_NAMES
    assert "apple_recheck_permissions" in tools.REGISTERED_TOOL_NAMES
    assert "apple_get_preferences" in tools.REGISTERED_TOOL_NAMES
    assert "apple_detect_defaults" in tools.REGISTERED_TOOL_NAMES
    assert "apple_update_contact_preferences" in tools.REGISTERED_TOOL_NAMES
    assert "apple_list_prompts" in tools.REGISTERED_TOOL_NAMES
    assert "apple_get_prompt" in tools.REGISTERED_TOOL_NAMES
    assert "apple_preview_communication" in tools.REGISTERED_TOOL_NAMES
    assert "apple_send_communication" in tools.REGISTERED_TOOL_NAMES
    assert "apple_preview_archive_message" in tools.REGISTERED_TOOL_NAMES
    assert "apple_list_recent_actions" in tools.REGISTERED_TOOL_NAMES
    assert "apple_undo_action" in tools.REGISTERED_TOOL_NAMES
    assert "apple_send_message_interactive" in tools.REGISTERED_TOOL_NAMES
    assert "apple_create_event_interactive" in tools.REGISTERED_TOOL_NAMES
    assert "apple_archive_message" in tools.REGISTERED_TOOL_NAMES
    assert "apple_capture_follow_up_from_mail" in tools.REGISTERED_TOOL_NAMES
    assert "apple_suggest_files" in tools.REGISTERED_TOOL_NAMES
    assert "apple_suggest_running_apps" in tools.REGISTERED_TOOL_NAMES
    assert "apple_suggest_places" in tools.REGISTERED_TOOL_NAMES
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
    assert "files_prepare_attachment" in prompt_names
    assert "files_organize_workspace" in prompt_names
    assert "system_capture_context" in prompt_names
    assert "maps_plan_route" in prompt_names


def test_all_prompts_have_descriptions() -> None:
    async def load_prompts():
        return await tools.mcp.list_prompts()

    prompts = asyncio.run(load_prompts())

    assert prompts
    assert all(prompt.description for prompt in prompts)


def test_subscription_handlers_registered() -> None:
    assert types.SubscribeRequest in tools.mcp._mcp_server.request_handlers
    assert types.UnsubscribeRequest in tools.mcp._mcp_server.request_handlers


def test_conformance_mode_registers_expected_surface() -> None:
    server = FastMCP("Conformance Test Server")

    enable_conformance_mode(server)

    async def load_state():
        prompt_names = {prompt.name: prompt for prompt in await server.list_prompts()}
        resource_names = {resource.name: resource for resource in await server.list_resources()}
        tool_names = {tool.name for tool in await server.list_tools()}
        return prompt_names, resource_names, tool_names

    prompt_names, resource_names, tool_names = asyncio.run(load_state())

    assert "test_simple_prompt" in prompt_names
    assert prompt_names["test_simple_prompt"].description
    assert "conformance_static_text" in resource_names
    assert resource_names["conformance_static_text"].description
    assert "test_image_content" in tool_names
    assert types.SetLevelRequest in server._mcp_server.request_handlers
    assert types.SubscribeRequest in server._mcp_server.request_handlers
    assert types.UnsubscribeRequest in server._mcp_server.request_handlers
    assert types.CompleteRequest in server._mcp_server.request_handlers


def test_task_tool_definitions_are_optional() -> None:
    definitions = tools._task_tool_definitions()

    assert {tool.name for tool in definitions} == {
        "apple_generate_daily_briefing",
        "apple_generate_weekly_briefing",
        "apple_triage_communications_task",
    }
    assert all(tool.execution is not None for tool in definitions)
    assert all(tool.execution.taskSupport == types.TASK_OPTIONAL for tool in definitions)


def test_conformance_prompts_preserve_non_text_content() -> None:
    server = FastMCP("Conformance Test Server")

    enable_conformance_mode(server)

    async def load_prompt_messages():
        prompt_with_resource = await server.get_prompt(
            "test_prompt_with_embedded_resource",
            {"resourceUri": "test://example-resource"},
        )
        prompt_with_image = await server.get_prompt("test_prompt_with_image")
        return prompt_with_resource.messages, prompt_with_image.messages

    resource_messages, image_messages = asyncio.run(load_prompt_messages())

    assert resource_messages[0].content.type == "resource"
    assert str(resource_messages[0].content.resource.uri) == "test://example-resource"
    assert image_messages[0].content.type == "image"
    assert image_messages[0].content.mimeType == "image/png"


def test_apple_health_aggregates_domains(monkeypatch) -> None:
    monkeypatch.setattr(tools, "mail_health", lambda: {"ok": True, "server_name": "Mail"})
    monkeypatch.setattr(tools, "calendar_health", lambda: {"ok": True, "server_name": "Calendar"})
    monkeypatch.setattr(tools, "reminders_health", lambda: {"ok": True, "server_name": "Reminders"})
    monkeypatch.setattr(tools, "messages_health", lambda: {"ok": True, "server_name": "Messages"})
    monkeypatch.setattr(tools, "contacts_health", lambda: {"ok": True, "server_name": "Contacts"})
    monkeypatch.setattr(tools, "notes_health", lambda: {"ok": True, "server_name": "Notes"})
    monkeypatch.setattr(tools, "shortcuts_health", lambda: {"ok": True, "server_name": "Shortcuts"})
    monkeypatch.setattr(tools, "files_health", lambda: {"ok": True, "server_name": "Files"})
    monkeypatch.setattr(tools, "system_health", lambda: {"ok": True, "server_name": "System"})
    monkeypatch.setattr(tools, "maps_health", lambda: {"ok": True, "server_name": "Maps"})

    result = tools.apple_health()

    assert result.ok is True
    assert result.domains["contacts"]["server_name"] == "Contacts"
    assert result.domains["mail"]["server_name"] == "Mail"
    assert result.domains["shortcuts"]["server_name"] == "Shortcuts"
    assert result.domains["files"]["server_name"] == "Files"
    assert result.domains["system"]["server_name"] == "System"
    assert result.domains["maps"]["server_name"] == "Maps"


def test_apple_list_prompts_fallback(monkeypatch) -> None:
    async def fake_list_prompts():
        return [type("Prompt", (), {"name": "apple_route_request", "title": "Route", "description": "desc", "arguments": []})()]

    monkeypatch.setattr(tools.mcp, "list_prompts", fake_list_prompts)

    payload = asyncio.run(tools.apple_list_prompts())

    assert payload["ok"] is True
    assert payload["prompts"][0]["name"] == "apple_route_request"


def test_apple_get_prompt_fallback(monkeypatch) -> None:
    async def fake_get_prompt(name: str, arguments: dict[str, object] | None = None):
        assert name == "apple_route_request"
        assert arguments == {"intent": "mail"}
        return type(
            "PromptResult",
            (),
            {
                "description": "desc",
                "messages": [
                    type(
                        "PromptMessage",
                        (),
                        {
                            "role": "user",
                            "content": type("Content", (), {"model_dump": lambda self, mode="json": {"type": "text", "text": "hello"}})(),
                        },
                    )()
                ],
            },
        )()

    monkeypatch.setattr(tools.mcp, "get_prompt", fake_get_prompt)

    payload = asyncio.run(tools.apple_get_prompt("apple_route_request", arguments_json='{"intent":"mail"}'))

    assert payload["ok"] is True
    assert payload["messages"][0]["content"]["text"] == "hello"


def test_apple_today_resource_combines_domain_payloads(monkeypatch) -> None:
    monkeypatch.setattr(tools, "system_status_resource", lambda: json.dumps({"frontmost_app": "Mail"}))
    monkeypatch.setattr(tools, "calendar_events_today_resource", lambda: json.dumps({"events": [{"title": "Standup"}]}))
    monkeypatch.setattr(tools, "reminders_today_resource", lambda: json.dumps({"reminders": [{"title": "Ship"}]}))
    monkeypatch.setattr(tools, "messages_unread_resource", lambda: json.dumps({"conversations": [{"chat_id": "1"}]}))
    monkeypatch.setattr(tools, "notes_recent_resource", lambda: json.dumps({"notes": [{"title": "Prep"}]}))
    monkeypatch.setattr(tools, "files_recent_resource", lambda: json.dumps({"files": [{"path": "/tmp/a.txt"}]}))

    payload = json.loads(tools.apple_today_resource())

    assert payload["system_status"]["frontmost_app"] == "Mail"
    assert payload["calendar_today"]["events"][0]["title"] == "Standup"
    assert payload["reminders_today"]["reminders"][0]["title"] == "Ship"
    assert payload["files_recent"]["files"][0]["path"] == "/tmp/a.txt"


def test_apple_overview_resource_includes_files_system_and_maps(monkeypatch) -> None:
    monkeypatch.setattr(tools, "_get_preferences", lambda: {"ok": True, "preferred_communication_channel": "auto"})
    monkeypatch.setattr(
        tools,
        "_domain_health",
        lambda: {
            "mail": {"ok": True},
            "calendar": {"ok": True},
            "reminders": {"ok": True},
            "messages": {"ok": True},
            "contacts": {"ok": True},
            "notes": {"ok": True},
            "shortcuts": {"ok": True},
            "files": {"ok": True},
            "system": {"ok": True},
            "maps": {"ok": True},
        },
    )
    monkeypatch.setattr(tools, "files_recent_resource", lambda: json.dumps({"files": []}))
    monkeypatch.setattr(tools, "system_status_resource", lambda: json.dumps({"frontmost_app": "Mail"}))
    monkeypatch.setattr(tools, "maps_status_resource", lambda: json.dumps({"helper_available": True}))
    monkeypatch.setattr(tools, "calendar_calendars_resource", lambda: json.dumps({"calendars": []}))
    monkeypatch.setattr(tools, "reminders_lists_resource", lambda: json.dumps({"lists": []}))
    monkeypatch.setattr(tools, "messages_recent_resource", lambda: json.dumps({"conversations": []}))
    monkeypatch.setattr(tools, "contacts_directory_resource", lambda: json.dumps({"contacts": []}))
    monkeypatch.setattr(tools, "notes_recent_resource", lambda: json.dumps({"notes": []}))
    monkeypatch.setattr(tools, "shortcuts_all_resource", lambda: json.dumps({"shortcuts": []}))
    monkeypatch.setattr(tools, "_mailboxes_resource", lambda: json.dumps({"mailboxes": []}))

    payload = json.loads(tools.apple_overview_resource())

    assert payload["health"]["files"]["ok"] is True
    assert payload["health"]["system"]["ok"] is True
    assert payload["health"]["maps"]["ok"] is True
    assert payload["resources"]["files"]["files"] == []
    assert payload["resources"]["system"]["frontmost_app"] == "Mail"
    assert payload["resources"]["maps"]["helper_available"] is True


def test_apple_permission_guide_supports_files_system_and_maps() -> None:
    files_guide = tools.apple_permission_guide("files")
    system_guide = tools.apple_permission_guide("system")
    maps_guide = tools.apple_permission_guide("maps")

    assert files_guide.domain == "files"
    assert files_guide.can_prompt_in_app is False
    assert any("allowed root" in step.lower() or "apple_files_mcp_allowed_roots" in step.lower() for step in files_guide.steps)
    assert system_guide.domain == "system"
    assert len(system_guide.steps) > 0
    assert maps_guide.domain == "maps"
    assert maps_guide.requires_manual_system_settings is False
    assert len(maps_guide.steps) > 0


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


def test_apple_detect_defaults_persists_preferences(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("APPLE_AGENT_MCP_STATE_FILE", str(tmp_path / "prefs.json"))
    load_settings.cache_clear()

    monkeypatch.setattr(
        tools,
        "mail_list_mailboxes",
        lambda account=None: type(
            "MailboxResponse",
            (),
            {"mailboxes": [type("Mailbox", (), {"account": "iCloud", "name": "Archive"})()]},
        )(),
    )
    monkeypatch.setattr(
        tools,
        "calendar_list_calendars",
        lambda: type(
            "CalendarResponse",
            (),
            {"ok": True, "calendars": [type("Calendar", (), {"calendar_id": "cal-1", "name": "Work", "writable": True})()]},
        )(),
    )
    monkeypatch.setattr(
        tools,
        "reminders_list_lists",
        lambda: type(
            "RemindersResponse",
            (),
            {"ok": True, "lists": [type("ReminderList", (), {"list_id": "list-1", "title": "General"})()]},
        )(),
    )
    monkeypatch.setattr(
        tools,
        "notes_list_folders",
        lambda limit=100, offset=0: type(
            "NotesResponse",
            (),
            {"ok": True, "folders": [type("Folder", (), {"folder_id": "folder-1", "name": "Notes", "account_name": "iCloud"})()]},
        )(),
    )

    result = tools.apple_detect_defaults()

    assert result.ok is True
    assert result.preferences.default_archive_mailbox == "Archive"
    assert result.preferences.default_calendar_id == "cal-1"
    assert result.preferences.default_reminder_list_id == "list-1"
    assert result.preferences.default_notes_folder_id == "folder-1"


def test_apple_prepare_communication_uses_contact_and_preferences(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("APPLE_AGENT_MCP_STATE_FILE", str(tmp_path / "prefs.json"))
    load_settings.cache_clear()
    tools.apple_update_preferences(preferred_communication_channel="messages", preferred_message_channel="phone")

    monkeypatch.setattr(
        tools,
        "contacts_search_contacts",
        lambda query, limit=10: type(
            "SearchResponse",
            (),
            {
                "count": 1,
                "contacts": [
                    type(
                        "ContactSummary",
                        (),
                        {"contact_id": "contact-1", "name": "Alice Doe"},
                    )()
                ],
            },
        )(),
    )
    monkeypatch.setattr(
        tools,
        "contacts_get_contact",
        lambda contact_id: type(
            "ContactResponse",
            (),
            {
                "contact": ContactDetail(
                    contact_id=contact_id,
                    name="Alice Doe",
                    first_name="Alice",
                    last_name="Doe",
                    organization="",
                    phone_count=1,
                    email_count=1,
                    phones=[ContactMethod(label="mobile", value="+15551234567")],
                    emails=[ContactMethod(label="work", value="alice@example.com")],
                    note="",
                )
            },
        )(),
    )

    result = tools.apple_prepare_communication("Alice Doe")

    assert result.ok is True
    assert result.recommended_channel == "messages"
    assert result.recommended_target == "+15551234567"


def test_apple_prepare_communication_uses_contact_specific_preferences(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("APPLE_AGENT_MCP_STATE_FILE", str(tmp_path / "prefs.json"))
    load_settings.cache_clear()
    tools.apple_update_preferences(preferred_communication_channel="messages", preferred_message_channel="phone")
    tools.apple_update_contact_preferences(
        contact_id="contact-1",
        preferred_communication_channel="mail",
        preferred_mail_address="alice+vip@example.com",
    )

    monkeypatch.setattr(
        tools,
        "contacts_search_contacts",
        lambda query, limit=10: type(
            "SearchResponse",
            (),
            {
                "count": 1,
                "contacts": [
                    type(
                        "ContactSummary",
                        (),
                        {"contact_id": "contact-1", "name": "Alice Doe"},
                    )()
                ],
            },
        )(),
    )
    monkeypatch.setattr(
        tools,
        "contacts_get_contact",
        lambda contact_id: type(
            "ContactResponse",
            (),
            {
                "contact": ContactDetail(
                    contact_id=contact_id,
                    name="Alice Doe",
                    first_name="Alice",
                    last_name="Doe",
                    organization="",
                    phone_count=1,
                    email_count=2,
                    phones=[ContactMethod(label="mobile", value="+15551234567")],
                    emails=[
                        ContactMethod(label="work", value="alice@example.com"),
                        ContactMethod(label="vip", value="alice+vip@example.com"),
                    ],
                    note="",
                )
            },
        )(),
    )

    result = tools.apple_prepare_communication("Alice Doe")

    assert result.ok is True
    assert result.recommended_channel == "mail"
    assert result.recommended_target == "alice+vip@example.com"


def test_apple_send_communication_routes_to_mail_with_default_account(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("APPLE_AGENT_MCP_STATE_FILE", str(tmp_path / "prefs.json"))
    load_settings.cache_clear()
    tools.apple_update_preferences(default_mail_account="jonathanrayreed@gmail.com", preferred_communication_channel="mail")

    monkeypatch.setattr(tools, "_looks_like_message_address", lambda value: "@" in value)
    captured: dict[str, object] = {}

    def fake_mail_send_message(to, cc=None, bcc=None, subject="", body="", attachments=None, from_account=None):
        captured["to"] = to
        captured["subject"] = subject
        captured["body"] = body
        captured["from_account"] = from_account
        return {"sent": True, "to": to, "from_account": from_account}

    monkeypatch.setattr(tools, "mail_send_message", fake_mail_send_message)

    result = tools.apple_send_communication("alice@example.com", "hello", subject="Hi")

    assert result.ok is True
    assert result.channel == "mail"
    assert result.action_id is not None
    assert captured["from_account"] == "jonathanrayreed@gmail.com"
    assert captured["to"] == ["alice@example.com"]


def test_apple_preview_communication_reports_execution_plan(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("APPLE_AGENT_MCP_STATE_FILE", str(tmp_path / "prefs.json"))
    load_settings.cache_clear()
    tools.apple_update_preferences(default_mail_account="jonathanrayreed@gmail.com", preferred_communication_channel="mail")

    monkeypatch.setattr(tools, "_looks_like_message_address", lambda value: "@" in value)

    result = tools.apple_preview_communication("alice@example.com", "hello", subject="Hi")

    assert result.ok is True
    assert result.execution_tool == "apple_send_communication"
    assert result.execution_arguments["recipient"] == "alice@example.com"
    assert result.undo_supported is False


def test_apple_archive_message_uses_detected_archive(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("APPLE_AGENT_MCP_STATE_FILE", str(tmp_path / "prefs.json"))
    load_settings.cache_clear()

    monkeypatch.setattr(
        tools,
        "mail_list_mailboxes",
        lambda account=None: type(
            "MailboxResponse",
            (),
            {"mailboxes": [type("Mailbox", (), {"account": "iCloud", "name": "Archive"})()]},
        )(),
    )
    monkeypatch.setattr(
        tools,
        "mail_get_message",
        lambda message_id: type(
            "MessageRecord",
            (),
            {
                "message_id": message_id,
                "subject": "Project update",
                "mailbox": "Inbox",
                "account": "iCloud",
            },
        )(),
    )
    monkeypatch.setattr(
        tools,
        "mail_move_message",
        lambda message_id, target_mailbox, target_account=None: type(
            "MoveRecord",
            (),
            {"message_id": message_id, "moved": True, "target_mailbox": target_mailbox},
        )(),
    )

    result = tools.apple_archive_message("msg-1")

    assert result.moved is True
    assert result.target_mailbox == "Archive"


def test_apple_archive_message_records_undoable_action(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("APPLE_AGENT_MCP_STATE_FILE", str(tmp_path / "prefs.json"))
    load_settings.cache_clear()
    tools.apple_update_preferences(default_archive_mailbox="Archive", default_archive_account="iCloud")

    captured: list[tuple[str, str, str | None]] = []

    monkeypatch.setattr(
        tools,
        "mail_get_message",
        lambda message_id: type(
            "MessageRecord",
            (),
            {
                "message_id": message_id,
                "subject": "Project update",
                "mailbox": "Inbox",
                "account": "iCloud",
            },
        )(),
    )

    def fake_move_message(message_id, target_mailbox, target_account=None):
        captured.append((message_id, target_mailbox, target_account))
        return type(
            "MoveRecord",
            (),
            {"message_id": message_id, "moved": True, "target_mailbox": target_mailbox},
        )()

    monkeypatch.setattr(tools, "mail_move_message", fake_move_message)

    tools.apple_archive_message("msg-1")
    actions = tools.apple_list_recent_actions()
    undo = tools.apple_undo_action(actions.actions[0].action_id)

    assert actions.count == 1
    assert actions.actions[0].undo_supported is True
    assert undo.ok is True
    assert undo.action.undo_status == "undone"
    assert captured == [("msg-1", "Archive", "iCloud"), ("msg-1", "Inbox", "iCloud")]


def test_apple_capture_follow_up_from_mail_uses_defaults(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("APPLE_AGENT_MCP_STATE_FILE", str(tmp_path / "prefs.json"))
    load_settings.cache_clear()
    tools.apple_update_preferences(default_reminder_list_id="list-1", default_notes_folder_id="folder-1")

    monkeypatch.setattr(
        tools,
        "mail_get_message",
        lambda message_id: type(
            "MessageRecord",
            (),
            {
                "message_id": message_id,
                "subject": "Project update",
                "sender": "boss@example.com",
                "date_received": "2026-04-01 09:00:00",
                "to": ["jonathan@example.com"],
                "cc": [],
                "body_text": "Need a follow-up tomorrow.",
            },
        )(),
    )
    monkeypatch.setattr(
        tools,
        "reminders_create_reminder",
        lambda title, list_id, notes=None, due_date=None, priority=0: type(
            "ReminderResponse",
            (),
            {"ok": True, "reminder": {"title": title, "list_id": list_id}},
        )(),
    )
    monkeypatch.setattr(
        tools,
        "notes_create_note",
        lambda title, folder_id, body_html=None, tags=None: type(
            "NoteResponse",
            (),
            {"ok": True, "note": {"title": title, "folder_id": folder_id}},
        )(),
    )

    result = tools.apple_capture_follow_up_from_mail("msg-1", due_date="2026-04-02T09:00:00-05:00")

    assert result.ok is True
    assert result.reminder is not None
    assert result.note is not None
    assert result.warnings == []


def test_apple_event_collaboration_summary_counts_attendees(monkeypatch) -> None:
    monkeypatch.setattr(
        tools,
        "calendar_get_event",
        lambda event_id: type(
            "EventResponse",
            (),
            {
                "event": type(
                    "Event",
                    (),
                    {
                        "event_id": event_id,
                        "title": "Weekly sync",
                        "calendar_name": "Work",
                        "attendees": [
                            type("Attendee", (), {"model_dump": lambda self: {"email": "a@example.com", "status": "accepted"}})(),
                            type("Attendee", (), {"model_dump": lambda self: {"email": "b@example.com", "status": "pending"}})(),
                        ],
                    },
                )()
            },
        )(),
    )

    result = tools.apple_event_collaboration_summary("event-1")

    assert result.ok is True
    assert result.attendee_count == 2
    assert result.accepted_count == 1
    assert result.pending_count == 1


def test_notes_append_wrapper_passes_body_text(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_append(note_id, body_text=None, body_html=None):
        captured["note_id"] = note_id
        captured["body_text"] = body_text
        captured["body_html"] = body_html
        return {"ok": True}

    monkeypatch.setattr(tools, "_notes_append_to_note", fake_append)

    tools.notes_append_to_note("note-1", "hello")

    assert captured == {"note_id": "note-1", "body_text": "hello", "body_html": None}


def test_messages_send_attachment_wrapper_passes_text(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_send_attachment(recipient, file_path, text=None):
        captured["recipient"] = recipient
        captured["file_path"] = file_path
        captured["text"] = text
        return {"ok": True}

    monkeypatch.setattr(tools, "_messages_send_attachment", fake_send_attachment)

    tools.messages_send_attachment("+15551234567", "/tmp/test.png", text="hello")

    assert captured == {"recipient": "+15551234567", "file_path": "/tmp/test.png", "text": "hello"}


def test_main_uses_streamable_http_settings(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("APPLE_AGENT_MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("APPLE_AGENT_MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("APPLE_AGENT_MCP_PORT", "8765")
    monkeypatch.setenv("APPLE_AGENT_MCP_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("APPLE_AGENT_MCP_STATE_FILE", str(tmp_path / "prefs.json"))
    load_settings.cache_clear()

    captured: dict[str, object] = {}

    def fake_run(*, transport: str) -> None:
        captured["transport"] = transport
        captured["host"] = tools.mcp.settings.host
        captured["port"] = tools.mcp.settings.port
        captured["log_level"] = tools.mcp.settings.log_level
        captured["stateless_http"] = tools.mcp.settings.stateless_http
        captured["json_response"] = tools.mcp.settings.json_response

    monkeypatch.setattr(tools.mcp, "run", fake_run)

    tools.main()

    assert captured == {
        "transport": "streamable-http",
        "host": "0.0.0.0",
        "port": 8765,
        "log_level": "DEBUG",
        "stateless_http": True,
        "json_response": True,
    }


def test_main_uses_streaming_http_for_conformance_mode(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("APPLE_AGENT_MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("APPLE_AGENT_MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("APPLE_AGENT_MCP_PORT", "8765")
    monkeypatch.setenv("APPLE_AGENT_MCP_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("APPLE_AGENT_MCP_CONFORMANCE_MODE", "true")
    monkeypatch.setenv("APPLE_AGENT_MCP_STATE_FILE", str(tmp_path / "prefs.json"))
    load_settings.cache_clear()

    captured: dict[str, object] = {}

    def fake_run(*, transport: str) -> None:
        captured["transport"] = transport
        captured["stateless_http"] = tools.mcp.settings.stateless_http
        captured["json_response"] = tools.mcp.settings.json_response

    monkeypatch.setattr(tools.mcp, "run", fake_run)

    tools.main()

    assert captured == {
        "transport": "streamable-http",
        "stateless_http": False,
        "json_response": False,
    }


def test_apple_create_reminder_and_note_record_actions(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("APPLE_AGENT_MCP_STATE_FILE", str(tmp_path / "prefs.json"))
    load_settings.cache_clear()
    tools.apple_update_preferences(default_reminder_list_id="list-1", default_notes_folder_id="folder-1")

    monkeypatch.setattr(
        tools,
        "reminders_create_reminder",
        lambda title, list_id, notes=None, due_date=None, priority=0: type(
            "ReminderResponse",
            (),
            {
                "ok": True,
                "reminder": type(
                    "Reminder",
                    (),
                    {"reminder_id": "rem-1", "title": title},
                )(),
            },
        )(),
    )
    monkeypatch.setattr(
        tools,
        "notes_create_note",
        lambda title, folder_id, body_html=None, tags=None: type(
            "NoteResponse",
            (),
            {
                "ok": True,
                "note": type(
                    "Note",
                    (),
                    {"note_id": "note-1", "title": title},
                )(),
            },
        )(),
    )

    reminder = tools.apple_create_reminder_with_defaults("Follow up")
    note = tools.apple_create_note_with_defaults("Reference", body_text="hello")
    actions = tools.apple_list_recent_actions(limit=5)

    assert reminder.ok is True
    assert note.ok is True
    assert actions.count == 2
    assert {action.action_type for action in actions.actions} == {"create_reminder", "create_note"}


def teardown_function() -> None:
    load_settings.cache_clear()
