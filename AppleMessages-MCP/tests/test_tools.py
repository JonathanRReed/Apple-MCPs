from apple_messages_mcp.config import load_settings
from apple_messages_mcp.models import AttachmentRecord, ConversationRecord, ConversationSummary, MessageRecord, MessagesCapabilities, ParticipantRecord
from apple_messages_mcp import tools
import asyncio


class FakeDBBridge:
    def history_accessible(self) -> bool:
        return True

    def history_access_diagnostic(self):
        return True, None

    def list_conversations(self, limit=25, offset=0, unread_only=False):
        return [
            ConversationSummary(
                chat_id="chat-guid-1",
                guid="chat-guid-1",
                display_name="Alice",
                service_name="iMessage",
                participants=[ParticipantRecord(handle_id="+15551234567", address="+15551234567", service="iMessage")],
                unread_count=1,
                last_activity_at="2026-03-28T10:00:00-05:00",
                last_message_preview="hello",
            )
        ]

    def get_conversation(self, chat_id: str, limit=50, offset=0):
        return ConversationRecord(
            chat_id=chat_id,
            guid=chat_id,
            display_name="Alice",
            service_name="iMessage",
            participants=[ParticipantRecord(handle_id="+15551234567", address="+15551234567", service="iMessage")],
            unread_count=1,
            last_activity_at="2026-03-28T10:00:00-05:00",
            last_message_preview="hello",
            messages=[
                MessageRecord(
                    message_id="msg-1",
                    guid="msg-1",
                    chat_id=chat_id,
                    sender=ParticipantRecord(handle_id="+15551234567", address="+15551234567", service="iMessage"),
                    text="hello",
                    subject=None,
                    service_name="iMessage",
                    sent_at="2026-03-28T10:00:00-05:00",
                    is_from_me=False,
                    has_attachments=False,
                )
            ],
        )

    def get_message(self, message_id: str):
        return self.get_conversation("chat-guid-1").messages[0]

    def search_messages(self, **kwargs):
        return [self.get_message("msg-1")]

    def list_attachments(self, **kwargs):
        return [AttachmentRecord(attachment_id="att-1", message_id="msg-1", path="/tmp/file.png", transfer_name="file.png", mime_type="image/png")]

    def participant_addresses_for_chat(self, chat_id: str):
        if chat_id == "group-chat-guid":
            return ["+15551234567", "+15557654321"]
        return ["+15551234567"]


class FakeAutomationBridge:
    def automation_accessible(self) -> bool:
        return True

    def automation_access_diagnostic(self):
        return True, None

    def send_message(self, recipient: str, text: str, service_name: str | None = None):
        return {"sent": True, "recipient": recipient, "text": text, "service_name": service_name or "iMessage"}

    def send_to_group(self, chat_id: str, text: str):
        return {"sent": True, "chat_id": chat_id, "text": text}

    def send_attachment(self, recipient: str, file_path: str, text: str | None = None):
        return {"sent": True, "recipient": recipient, "file_path": file_path, "text": text}


def test_messages_health_reports_capabilities(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_MESSAGES_MCP_SAFETY_MODE", "full_access")
    load_settings.cache_clear()
    monkeypatch.setattr(tools, "_db_bridge", lambda: FakeDBBridge())
    monkeypatch.setattr(tools, "_automation_bridge", lambda: FakeAutomationBridge())

    result = tools.messages_health()

    assert result.ok is True
    assert result.capabilities == MessagesCapabilities(
        can_read_history=True,
        can_send_messages=True,
        can_reply_in_existing_chat=True,
        requires_full_disk_access=True,
        requires_messages_automation=True,
    )


def test_messages_reply_in_conversation_returns_send_response(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_MESSAGES_MCP_SAFETY_MODE", "full_access")
    load_settings.cache_clear()
    monkeypatch.setattr(tools, "_db_bridge", lambda: FakeDBBridge())
    monkeypatch.setattr(tools, "_automation_bridge", lambda: FakeAutomationBridge())

    result = tools.messages_reply_in_conversation("chat-guid-1", "hi")

    assert result.ok is True
    assert result.sent is True


def test_messages_reply_in_group_conversation_returns_chat_id(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_MESSAGES_MCP_SAFETY_MODE", "full_access")
    load_settings.cache_clear()
    monkeypatch.setattr(tools, "_db_bridge", lambda: FakeDBBridge())
    monkeypatch.setattr(tools, "_automation_bridge", lambda: FakeAutomationBridge())

    result = tools.messages_reply_in_conversation("group-chat-guid", "hi group")

    assert result.ok is True
    assert result.chat_id == "group-chat-guid"
    assert result.recipient is None


def test_messages_send_attachment_accepts_optional_text(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_MESSAGES_MCP_SAFETY_MODE", "full_access")
    load_settings.cache_clear()
    monkeypatch.setattr(tools, "_db_bridge", lambda: FakeDBBridge())
    monkeypatch.setattr(tools, "_automation_bridge", lambda: FakeAutomationBridge())

    result = tools.messages_send_attachment("+15551234567", "/tmp/test.png")

    assert result.ok is True
    assert result.file_path == "/tmp/test.png"
    assert result.text is None


def test_messages_health_surfaces_permission_errors(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_MESSAGES_MCP_SAFETY_MODE", "full_access")
    load_settings.cache_clear()

    class BrokenDBBridge(FakeDBBridge):
        def history_access_diagnostic(self):
            from apple_messages_mcp.messages_db_bridge import MessagesDBBridgeError

            return False, MessagesDBBridgeError(
                "PERMISSION_DENIED",
                "Full Disk Access is required to read Apple Messages history.",
                "Grant Full Disk Access to the host app or terminal and retry.",
            )

    monkeypatch.setattr(tools, "_db_bridge", lambda: BrokenDBBridge())
    monkeypatch.setattr(tools, "_automation_bridge", lambda: FakeAutomationBridge())

    result = tools.messages_health()

    assert result.history_access is False
    assert result.history_access_error == "Full Disk Access is required to read Apple Messages history."


def test_messages_main_exists() -> None:
    assert callable(tools.main)


def test_messages_get_conversation_schema_uses_integer_limit() -> None:
    async def load_schema():
        tool_list = await tools.mcp.list_tools()
        return next(tool.inputSchema for tool in tool_list if tool.name == "messages_get_conversation")

    schema = asyncio.run(load_schema())

    assert schema["properties"]["limit"]["anyOf"] == [{"type": "integer"}, {"type": "string"}]


def test_messages_get_conversation_accepts_string_limit_and_offset(monkeypatch) -> None:
    monkeypatch.setenv("APPLE_MESSAGES_MCP_SAFETY_MODE", "full_access")
    load_settings.cache_clear()
    monkeypatch.setattr(tools, "_db_bridge", lambda: FakeDBBridge())
    monkeypatch.setattr(tools, "_automation_bridge", lambda: FakeAutomationBridge())

    result = tools.messages_get_conversation("chat-guid-1", limit="3", offset="0")

    assert result.ok is True
    assert result.conversation.chat_id == "chat-guid-1"


def teardown_function() -> None:
    load_settings.cache_clear()
