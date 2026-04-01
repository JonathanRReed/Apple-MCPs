from apple_mail_mcp.config import Settings
from apple_mail_mcp.models import AttachmentRecord, DeleteRecord, DraftRecord, ForwardRecord, MailboxRecord, MarkRecord, MessageRecord, MessageSummary, MoveRecord, ReplyRecord, SafetyProfile, SendRecord
from apple_mail_mcp.tools import create_server, health_tool, mail_archive_thread_tool, mail_compose_draft_tool, mail_delete_message_tool, mail_forward_message_tool, mail_get_message_tool, mail_get_thread_tool, mail_list_mailboxes_tool, mail_mark_message_tool, mail_move_message_tool, mail_reply_latest_in_thread_tool, mail_reply_message_tool, mail_search_messages, mail_search_messages_tool, mail_send_message_tool


class FakeBridge:
    def list_mailboxes(self, account: str | None = None) -> list[MailboxRecord]:
        if account:
            return [MailboxRecord(account=account, name="Inbox")]
        return [MailboxRecord(account="iCloud", name="Inbox")]

    def search_messages(
        self,
        query: str,
        mailbox: str | None = None,
        unread_only: bool = False,
        limit: int = 10,
    ) -> list[MessageSummary]:
        return [
            MessageSummary(
                message_id="id-1",
                subject=f"match:{query}",
                sender="boss@example.com",
                date_received="2026-03-27 09:15:00",
                mailbox=mailbox or "Inbox",
                account="iCloud",
                is_read=not unread_only,
                preview="Project update",
            )
        ][:limit]

    def get_message(self, message_id: str) -> MessageRecord:
        return MessageRecord(
            message_id=message_id,
            subject="Project update",
            sender="boss@example.com",
            date_received="2026-03-27 09:15:00",
            mailbox="Inbox",
            account="iCloud",
            is_read=False,
            preview="Project update",
            to=["jonathan@example.com"],
            cc=[],
            body_text="Full body",
            attachments=[AttachmentRecord(name="draft.pdf")],
        )

    def compose_draft(
        self,
        to: list[str],
        cc: list[str] | None,
        bcc: list[str] | None,
        subject: str,
        body: str,
        attachments: list[str] | None,
        visible: bool,
        from_account: str | None = None,
    ) -> DraftRecord:
        return DraftRecord(
            draft_id="draft-1",
            subject=subject,
            to=to,
            cc=cc or [],
            bcc=bcc or [],
            visible=visible,
            from_account=from_account,
        )

    def send_message(
        self,
        to: list[str],
        cc: list[str] | None,
        bcc: list[str] | None,
        subject: str,
        body: str,
        attachments: list[str] | None,
        from_account: str | None = None,
    ) -> SendRecord:
        return SendRecord(
            subject=subject,
            to=to,
            cc=cc or [],
            bcc=bcc or [],
            sent=True,
            from_account=from_account,
        )

    def reply_message(
        self,
        message_id: str,
        body: str,
        reply_all: bool = False,
        from_account: str | None = None,
    ) -> ReplyRecord:
        return ReplyRecord(sent=True, subject=f"Re:{message_id}", reply_all=reply_all, from_account=from_account)

    def forward_message(
        self,
        message_id: str,
        to: list[str],
        body: str = "",
        from_account: str | None = None,
    ) -> ForwardRecord:
        return ForwardRecord(sent=True, subject=f"Fwd:{message_id}", to=to, from_account=from_account)

    def mark_message(self, message_id: str, is_read: bool) -> MarkRecord:
        return MarkRecord(message_id=message_id, is_read=is_read)

    def move_message(
        self,
        message_id: str,
        target_mailbox: str,
        target_account: str | None = None,
    ) -> MoveRecord:
        return MoveRecord(message_id=message_id, moved=True, target_mailbox=target_mailbox)

    def delete_message(self, message_id: str) -> DeleteRecord:
        return DeleteRecord(message_id=message_id, deleted=True)


def test_health_tool_reports_settings() -> None:
    settings = Settings(safety_profile=SafetyProfile.SAFE_MANAGE, transport="stdio", visible_drafts=False)

    result = health_tool(settings)

    assert result.ok is True
    assert result.safety_profile == "safe_manage"
    assert result.visible_drafts is False


def test_list_mailboxes_tool_returns_structured_payload() -> None:
    result = mail_list_mailboxes_tool(FakeBridge(), account="iCloud")

    assert result.count == 1
    assert result.mailboxes[0].account == "iCloud"


def test_search_tool_bounds_limit_and_returns_results() -> None:
    settings = Settings(default_search_limit=25)

    result = mail_search_messages_tool(FakeBridge(), settings, query="project", unread_only=True, limit=0)

    assert result.count == 1
    assert result.results[0].subject == "match:project"


def test_get_message_tool_returns_full_message() -> None:
    result = mail_get_message_tool(FakeBridge(), message_id="id-1")

    assert result.message_id == "id-1"
    assert result.attachments[0].name == "draft.pdf"


def test_compose_draft_tool_respects_safety_policy() -> None:
    settings = Settings(safety_profile=SafetyProfile.SAFE_MANAGE, visible_drafts=False)

    result = mail_compose_draft_tool(
        FakeBridge(),
        settings,
        to=["jonathan@example.com"],
        cc=None,
        bcc=None,
        subject="Hello",
        body="Draft body",
        attachments=None,
    )

    assert result.draft_id == "draft-1"
    assert result.subject == "Hello"
    assert result.visible is False


def test_mail_search_messages_accepts_string_limit() -> None:
    settings = Settings(default_search_limit=25)

    result = mail_search_messages(query="project", unread_only=True, limit="5", bridge=FakeBridge(), settings=settings)

    assert result.count == 1
    assert result.results[0].subject == "match:project"


def test_compose_draft_passes_from_account() -> None:
    settings = Settings(safety_profile=SafetyProfile.SAFE_MANAGE, visible_drafts=True)

    result = mail_compose_draft_tool(
        FakeBridge(),
        settings,
        to=["test@example.com"],
        cc=None,
        bcc=None,
        subject="Test",
        body="Body",
        attachments=None,
        from_account="jonathanrayreed@gmail.com",
    )

    assert result.from_account == "jonathanrayreed@gmail.com"
    assert result.draft_id == "draft-1"


def test_compose_draft_from_account_defaults_to_none() -> None:
    settings = Settings(safety_profile=SafetyProfile.SAFE_MANAGE, visible_drafts=True)

    result = mail_compose_draft_tool(
        FakeBridge(),
        settings,
        to=["test@example.com"],
        cc=None,
        bcc=None,
        subject="Test",
        body="Body",
        attachments=None,
    )

    assert result.from_account is None


def test_send_message_passes_from_account() -> None:
    settings = Settings(safety_profile=SafetyProfile.FULL_ACCESS)

    result = mail_send_message_tool(
        FakeBridge(),
        settings,
        to=["test@example.com"],
        cc=None,
        bcc=None,
        subject="Sent",
        body="Body",
        attachments=None,
        from_account="jonathanrayreed@gmail.com",
    )

    assert result.sent is True
    assert result.from_account == "jonathanrayreed@gmail.com"


def test_send_message_from_account_defaults_to_none() -> None:
    settings = Settings(safety_profile=SafetyProfile.FULL_ACCESS)

    result = mail_send_message_tool(
        FakeBridge(),
        settings,
        to=["test@example.com"],
        cc=None,
        bcc=None,
        subject="Sent",
        body="Body",
        attachments=None,
    )

    assert result.sent is True
    assert result.from_account is None


def test_reply_forward_mark_move_and_delete_tools() -> None:
    settings = Settings(safety_profile=SafetyProfile.FULL_ACCESS)
    bridge = FakeBridge()

    reply = mail_reply_message_tool(bridge, settings, message_id="id-1", body="Thanks", reply_all=True)
    forward = mail_forward_message_tool(
        bridge,
        settings,
        message_id="id-1",
        to=["team@example.com"],
        body="FYI",
        from_account="jonathanrayreed@gmail.com",
    )
    marked = mail_mark_message_tool(bridge, settings, message_id="id-1", is_read=True)
    moved = mail_move_message_tool(bridge, settings, message_id="id-1", target_mailbox="Archive")
    deleted = mail_delete_message_tool(bridge, settings, message_id="id-1")

    assert reply.reply_all is True
    assert forward.to == ["team@example.com"]
    assert marked.is_read is True
    assert moved.target_mailbox == "Archive"
    assert deleted.deleted is True


def test_get_thread_groups_related_messages() -> None:
    settings = Settings(safety_profile=SafetyProfile.SAFE_READONLY)
    thread = mail_get_thread_tool(FakeBridge(), settings, message_id="id-1", limit=10)

    assert thread.count == 1
    assert thread.normalized_subject == "Project update"
    assert thread.messages[0].message_id == "id-1"


def test_reply_latest_in_thread_and_archive_thread() -> None:
    settings = Settings(safety_profile=SafetyProfile.FULL_ACCESS)
    bridge = FakeBridge()

    reply = mail_reply_latest_in_thread_tool(bridge, settings, message_id="id-1", body="latest")
    archived = mail_archive_thread_tool(bridge, settings, message_id="id-1", archive_mailbox="Archive")

    assert reply.sent is True
    assert archived.count == 1
    assert archived.affected_message_ids == ["id-1"]


def test_create_server_applies_http_settings() -> None:
    settings = Settings(transport="streamable-http", host="0.0.0.0", port=8765, log_level="DEBUG")

    server = create_server(settings=settings, bridge=FakeBridge())

    assert server.settings.host == "0.0.0.0"
    assert server.settings.port == 8765
    assert server.settings.log_level == "DEBUG"
    assert server.settings.stateless_http is True
    assert server.settings.json_response is True
