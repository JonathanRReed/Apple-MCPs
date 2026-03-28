from apple_mail_mcp.config import Settings
from apple_mail_mcp.models import AttachmentRecord, DraftRecord, MailboxRecord, MessageRecord, MessageSummary, SafetyProfile
from apple_mail_mcp.tools import health_tool, mail_compose_draft_tool, mail_get_message_tool, mail_list_mailboxes_tool, mail_search_messages, mail_search_messages_tool


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
    ) -> DraftRecord:
        return DraftRecord(
            draft_id="draft-1",
            subject=subject,
            to=to,
            cc=cc or [],
            bcc=bcc or [],
            visible=visible,
        )


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
