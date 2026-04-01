from __future__ import annotations

import json
import logging

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import Annotations, ToolAnnotations

from apple_mail_mcp.config import Settings, load_settings
from apple_mail_mcp.mail_bridge import AppleMailBridge, MailBridgeError
from apple_mail_mcp.models import DeleteRecord, DraftRecord, ErrorResponse, ForwardRecord, HealthResponse, MailboxListResponse, MarkRecord, MessageRecord, MessageSearchResponse, MoveRecord, ReplyRecord, SendRecord, ThreadMutationRecord, ThreadRecord, error_response, normalized_thread_subject
from apple_mail_mcp.permissions import SafetyPolicyError, ensure_tool_allowed

LOGGER = logging.getLogger("apple_mail_mcp")
SERVER_INSTRUCTIONS = (
    "Use this server for Apple Mail on macOS. "
    "Search here when the user wants to inspect mailboxes, search messages, read a specific message, create drafts, or send email. "
    "Prefer list and read tools before drafting or sending."
)


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))


def _resource_json(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, default=str)


def _coerce_int_arg(name: str, value: int | str, *, minimum: int | None = None) -> int:
    try:
        normalized = int(str(value).strip()) if isinstance(value, str) else int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if minimum is not None and normalized < minimum:
        comparator = "greater than zero" if minimum == 1 else f"at least {minimum}"
        raise ValueError(f"{name} must be {comparator}")
    return normalized


def health_tool(settings: Settings) -> HealthResponse:
    return HealthResponse(
        ok=True,
        server_name=settings.server_name,
        version=settings.version,
        safety_profile=settings.safety_profile.value,
        transport=settings.transport,
        visible_drafts=settings.visible_drafts,
        capabilities=[
            "list_mailboxes",
            "search_messages",
            "get_message",
            "get_thread",
            "compose_draft",
            "send_message",
            "reply_message",
            "forward_message",
            "mark_message",
            "move_message",
            "delete_message",
            "reply_latest_in_thread",
            "archive_thread",
            "resources",
            "prompts",
        ],
        supports=["stdio", "streamable-http"],
    )


def mailboxes_resource_tool(bridge: AppleMailBridge) -> str:
    mailboxes = bridge.list_mailboxes()
    return _resource_json({"mailboxes": [item.to_dict() for item in mailboxes], "count": len(mailboxes)})


def mail_inbox_triage_prompt_text() -> str:
    return (
        "Review Apple Mail for the most relevant messages, summarize the inbox state, "
        "and suggest next actions. Start with mailbox discovery and focused message search."
    )


def mail_draft_reply_prompt_text() -> str:
    return (
        "Use Apple Mail to find the relevant message, extract the important context, "
        "and draft a clear reply. Read the original message before composing a draft."
    )


def mail_health(settings: Settings | None = None) -> HealthResponse:
    return health_tool(settings or load_settings())


def mail_permission_guide() -> dict[str, object]:
    return {
        "ok": True,
        "domain": "mail",
        "can_prompt_in_app": True,
        "requires_manual_system_settings": False,
        "steps": [
            "Call a Mail tool from this MCP server.",
            "Approve the macOS Automation prompt for Mail if it appears.",
            "If access was denied before, re-enable it in System Settings > Privacy & Security > Automation.",
        ],
    }


async def mail_recheck_permissions(ctx: Context) -> HealthResponse:
    await ctx.report_progress(25, 100, "Rechecking Mail access")
    response = mail_health()
    await ctx.session.send_resource_list_changed()
    await ctx.report_progress(100, 100, "Done")
    return response


def mail_list_mailboxes_tool(bridge: AppleMailBridge, account: str | None = None) -> MailboxListResponse:
    mailboxes = bridge.list_mailboxes(account=account)
    return MailboxListResponse(mailboxes=mailboxes, count=len(mailboxes))


def mail_search_messages_tool(
    bridge: AppleMailBridge,
    settings: Settings,
    query: str,
    mailbox: str | None = None,
    unread_only: bool = False,
    limit: int = 10,
) -> MessageSearchResponse:
    bounded_limit = max(1, min(limit or settings.default_search_limit, 100))
    results = bridge.search_messages(
        query=query,
        mailbox=mailbox,
        unread_only=unread_only,
        limit=bounded_limit,
    )
    return MessageSearchResponse(results=results, count=len(results))


def mail_get_message_tool(bridge: AppleMailBridge, message_id: str) -> MessageRecord:
    return bridge.get_message(message_id)


def mail_compose_draft_tool(
    bridge: AppleMailBridge,
    settings: Settings,
    to: list[str],
    cc: list[str] | None,
    bcc: list[str] | None,
    subject: str,
    body: str,
    attachments: list[str] | None,
    from_account: str | None = None,
) -> DraftRecord:
    ensure_tool_allowed(settings.safety_profile, "mail_compose_draft")
    draft = bridge.compose_draft(
        to=to,
        cc=cc,
        bcc=bcc,
        subject=subject,
        body=body,
        attachments=attachments,
        visible=settings.visible_drafts,
        from_account=from_account,
    )
    LOGGER.info("mail_compose_draft ok subject=%s recipients=%s", subject, len(to))
    return draft


def mail_send_message_tool(
    bridge: AppleMailBridge,
    settings: Settings,
    to: list[str],
    cc: list[str] | None,
    bcc: list[str] | None,
    subject: str,
    body: str,
    attachments: list[str] | None,
    from_account: str | None = None,
) -> SendRecord:
    ensure_tool_allowed(settings.safety_profile, "mail_send_message")
    result = bridge.send_message(
        to=to,
        cc=cc,
        bcc=bcc,
        subject=subject,
        body=body,
        attachments=attachments,
        from_account=from_account,
    )
    LOGGER.info("mail_send_message ok subject=%s recipients=%s", subject, len(to))
    return result


def mail_reply_message_tool(
    bridge: AppleMailBridge,
    settings: Settings,
    message_id: str,
    body: str,
    reply_all: bool = False,
    from_account: str | None = None,
) -> ReplyRecord:
    ensure_tool_allowed(settings.safety_profile, "mail_reply_message")
    result = bridge.reply_message(
        message_id=message_id,
        body=body,
        reply_all=reply_all,
        from_account=from_account,
    )
    LOGGER.info("mail_reply_message ok message_id=%s reply_all=%s", message_id, reply_all)
    return result


def mail_forward_message_tool(
    bridge: AppleMailBridge,
    settings: Settings,
    message_id: str,
    to: list[str],
    body: str = "",
    from_account: str | None = None,
) -> ForwardRecord:
    ensure_tool_allowed(settings.safety_profile, "mail_forward_message")
    result = bridge.forward_message(
        message_id=message_id,
        to=to,
        body=body,
        from_account=from_account,
    )
    LOGGER.info("mail_forward_message ok message_id=%s recipients=%s", message_id, len(to))
    return result


def mail_mark_message_tool(
    bridge: AppleMailBridge,
    settings: Settings,
    message_id: str,
    is_read: bool,
) -> MarkRecord:
    ensure_tool_allowed(settings.safety_profile, "mail_mark_message")
    result = bridge.mark_message(message_id=message_id, is_read=is_read)
    LOGGER.info("mail_mark_message ok message_id=%s is_read=%s", message_id, is_read)
    return result


def mail_move_message_tool(
    bridge: AppleMailBridge,
    settings: Settings,
    message_id: str,
    target_mailbox: str,
    target_account: str | None = None,
) -> MoveRecord:
    ensure_tool_allowed(settings.safety_profile, "mail_move_message")
    result = bridge.move_message(
        message_id=message_id,
        target_mailbox=target_mailbox,
        target_account=target_account,
    )
    LOGGER.info("mail_move_message ok message_id=%s target=%s", message_id, target_mailbox)
    return result


def mail_delete_message_tool(
    bridge: AppleMailBridge,
    settings: Settings,
    message_id: str,
) -> DeleteRecord:
    ensure_tool_allowed(settings.safety_profile, "mail_delete_message")
    result = bridge.delete_message(message_id=message_id)
    LOGGER.info("mail_delete_message ok message_id=%s", message_id)
    return result


def mail_get_thread_tool(
    bridge: AppleMailBridge,
    settings: Settings,
    message_id: str,
    limit: int = 25,
) -> ThreadRecord:
    ensure_tool_allowed(settings.safety_profile, "mail_get_thread")
    anchor = bridge.get_message(message_id)
    normalized_subject = normalized_thread_subject(anchor.subject)
    search_query = normalized_subject or anchor.sender or "*"
    search_limit = max(25, min(limit * 4, 100))
    candidates = bridge.search_messages(
        query=search_query or "*",
        mailbox=anchor.mailbox,
        unread_only=False,
        limit=search_limit,
    )
    matched: list[object] = []
    seen: set[str] = set()
    for candidate in [*candidates, anchor]:
        candidate_subject = normalized_thread_subject(candidate.subject)
        if normalized_subject and candidate_subject.lower() != normalized_subject.lower():
            continue
        if candidate.message_id in seen:
            continue
        seen.add(candidate.message_id)
        matched.append(candidate)
    matched.sort(key=lambda item: item.date_received)
    page = matched[:limit]
    return ThreadRecord(
        message_id=anchor.message_id,
        normalized_subject=normalized_subject,
        anchor_subject=anchor.subject,
        mailbox=anchor.mailbox,
        account=anchor.account,
        messages=page,
        count=len(page),
    )


def mail_reply_latest_in_thread_tool(
    bridge: AppleMailBridge,
    settings: Settings,
    message_id: str,
    body: str,
    reply_all: bool = False,
    from_account: str | None = None,
    limit: int = 25,
) -> ReplyRecord:
    ensure_tool_allowed(settings.safety_profile, "mail_reply_latest_in_thread")
    thread = mail_get_thread_tool(bridge, settings, message_id=message_id, limit=limit)
    latest_message_id = thread.messages[-1].message_id if thread.messages else message_id
    return mail_reply_message_tool(
        bridge,
        settings,
        message_id=latest_message_id,
        body=body,
        reply_all=reply_all,
        from_account=from_account,
    )


def mail_archive_thread_tool(
    bridge: AppleMailBridge,
    settings: Settings,
    message_id: str,
    archive_mailbox: str = "Archive",
    archive_account: str | None = None,
    limit: int = 25,
) -> ThreadMutationRecord:
    ensure_tool_allowed(settings.safety_profile, "mail_archive_thread")
    thread = mail_get_thread_tool(bridge, settings, message_id=message_id, limit=limit)
    affected: list[str] = []
    for item in thread.messages:
        result = mail_move_message_tool(
            bridge,
            settings,
            message_id=item.message_id,
            target_mailbox=archive_mailbox,
            target_account=archive_account,
        )
        if result.moved:
            affected.append(result.message_id)
    return ThreadMutationRecord(
        anchor_message_id=message_id,
        normalized_subject=thread.normalized_subject,
        affected_message_ids=affected,
        count=len(affected),
    )


def mail_list_mailboxes(
    account: str | None = None,
    *,
    bridge: AppleMailBridge | None = None,
) -> MailboxListResponse | ErrorResponse:
    try:
        return mail_list_mailboxes_tool(bridge or AppleMailBridge(), account=account)
    except MailBridgeError as exc:
        return error_response("MAILBOX_LIST_FAILED", str(exc))


def mail_search_messages(
    query: str,
    mailbox: str | None = None,
    unread_only: bool = False,
    limit: int | str = 10,
    *,
    bridge: AppleMailBridge | None = None,
    settings: Settings | None = None,
) -> MessageSearchResponse | ErrorResponse:
    try:
        limit_value = _coerce_int_arg("limit", limit, minimum=1)
        return mail_search_messages_tool(
            bridge or AppleMailBridge(),
            settings or load_settings(),
            query=query,
            mailbox=mailbox,
            unread_only=unread_only,
            limit=limit_value,
        )
    except ValueError as exc:
        return error_response("INVALID_INPUT", str(exc))
    except MailBridgeError as exc:
        return error_response("MESSAGE_SEARCH_FAILED", str(exc))


def mail_get_message(
    message_id: str,
    *,
    bridge: AppleMailBridge | None = None,
) -> MessageRecord | ErrorResponse:
    try:
        return mail_get_message_tool(bridge or AppleMailBridge(), message_id=message_id)
    except MailBridgeError as exc:
        return error_response("MESSAGE_LOOKUP_FAILED", str(exc))


def mail_compose_draft(
    to: list[str],
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    subject: str = "",
    body: str = "",
    attachments: list[str] | None = None,
    from_account: str | None = None,
    *,
    bridge: AppleMailBridge | None = None,
    settings: Settings | None = None,
) -> DraftRecord | ErrorResponse:
    active_settings = settings or load_settings()
    try:
        return mail_compose_draft_tool(
            bridge or AppleMailBridge(),
            active_settings,
            to=to,
            cc=cc,
            bcc=bcc,
            subject=subject,
            body=body,
            attachments=attachments,
            from_account=from_account,
        )
    except SafetyPolicyError as exc:
        return error_response("SAFETY_POLICY_BLOCK", str(exc))
    except MailBridgeError as exc:
        return error_response("DRAFT_CREATE_FAILED", str(exc))


def mail_send_message(
    to: list[str],
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    subject: str = "",
    body: str = "",
    attachments: list[str] | None = None,
    from_account: str | None = None,
    *,
    bridge: AppleMailBridge | None = None,
    settings: Settings | None = None,
) -> SendRecord | ErrorResponse:
    active_settings = settings or load_settings()
    try:
        return mail_send_message_tool(
            bridge or AppleMailBridge(),
            active_settings,
            to=to,
            cc=cc,
            bcc=bcc,
            subject=subject,
            body=body,
            attachments=attachments,
            from_account=from_account,
        )
    except SafetyPolicyError as exc:
        return error_response("SAFETY_POLICY_BLOCK", str(exc))
    except MailBridgeError as exc:
        return error_response("SEND_FAILED", str(exc))


def mail_reply_message(
    message_id: str,
    body: str,
    reply_all: bool = False,
    from_account: str | None = None,
    *,
    bridge: AppleMailBridge | None = None,
    settings: Settings | None = None,
) -> ReplyRecord | ErrorResponse:
    active_settings = settings or load_settings()
    try:
        return mail_reply_message_tool(
            bridge or AppleMailBridge(),
            active_settings,
            message_id=message_id,
            body=body,
            reply_all=reply_all,
            from_account=from_account,
        )
    except SafetyPolicyError as exc:
        return error_response("SAFETY_POLICY_BLOCK", str(exc))
    except MailBridgeError as exc:
        return error_response("REPLY_FAILED", str(exc))


def mail_forward_message(
    message_id: str,
    to: list[str],
    body: str = "",
    from_account: str | None = None,
    *,
    bridge: AppleMailBridge | None = None,
    settings: Settings | None = None,
) -> ForwardRecord | ErrorResponse:
    active_settings = settings or load_settings()
    try:
        return mail_forward_message_tool(
            bridge or AppleMailBridge(),
            active_settings,
            message_id=message_id,
            to=to,
            body=body,
            from_account=from_account,
        )
    except SafetyPolicyError as exc:
        return error_response("SAFETY_POLICY_BLOCK", str(exc))
    except MailBridgeError as exc:
        return error_response("FORWARD_FAILED", str(exc))


def mail_mark_message(
    message_id: str,
    is_read: bool,
    *,
    bridge: AppleMailBridge | None = None,
    settings: Settings | None = None,
) -> MarkRecord | ErrorResponse:
    active_settings = settings or load_settings()
    try:
        return mail_mark_message_tool(
            bridge or AppleMailBridge(),
            active_settings,
            message_id=message_id,
            is_read=is_read,
        )
    except SafetyPolicyError as exc:
        return error_response("SAFETY_POLICY_BLOCK", str(exc))
    except MailBridgeError as exc:
        return error_response("MARK_FAILED", str(exc))


def mail_move_message(
    message_id: str,
    target_mailbox: str,
    target_account: str | None = None,
    *,
    bridge: AppleMailBridge | None = None,
    settings: Settings | None = None,
) -> MoveRecord | ErrorResponse:
    active_settings = settings or load_settings()
    try:
        return mail_move_message_tool(
            bridge or AppleMailBridge(),
            active_settings,
            message_id=message_id,
            target_mailbox=target_mailbox,
            target_account=target_account,
        )
    except SafetyPolicyError as exc:
        return error_response("SAFETY_POLICY_BLOCK", str(exc))
    except MailBridgeError as exc:
        return error_response("MOVE_FAILED", str(exc))


def mail_delete_message(
    message_id: str,
    *,
    bridge: AppleMailBridge | None = None,
    settings: Settings | None = None,
) -> DeleteRecord | ErrorResponse:
    active_settings = settings or load_settings()
    try:
        return mail_delete_message_tool(
            bridge or AppleMailBridge(),
            active_settings,
            message_id=message_id,
        )
    except SafetyPolicyError as exc:
        return error_response("SAFETY_POLICY_BLOCK", str(exc))
    except MailBridgeError as exc:
        return error_response("DELETE_FAILED", str(exc))


def mail_get_thread(
    message_id: str,
    limit: int | str = 25,
    *,
    bridge: AppleMailBridge | None = None,
    settings: Settings | None = None,
) -> ThreadRecord | ErrorResponse:
    active_settings = settings or load_settings()
    try:
        limit_value = _coerce_int_arg("limit", limit, minimum=1)
        return mail_get_thread_tool(bridge or AppleMailBridge(), active_settings, message_id=message_id, limit=limit_value)
    except ValueError as exc:
        return error_response("INVALID_INPUT", str(exc))
    except SafetyPolicyError as exc:
        return error_response("SAFETY_POLICY_BLOCK", str(exc))
    except MailBridgeError as exc:
        return error_response("THREAD_LOOKUP_FAILED", str(exc))


def mail_reply_latest_in_thread(
    message_id: str,
    body: str,
    reply_all: bool = False,
    from_account: str | None = None,
    limit: int | str = 25,
    *,
    bridge: AppleMailBridge | None = None,
    settings: Settings | None = None,
) -> ReplyRecord | ErrorResponse:
    active_settings = settings or load_settings()
    try:
        limit_value = _coerce_int_arg("limit", limit, minimum=1)
        return mail_reply_latest_in_thread_tool(
            bridge or AppleMailBridge(),
            active_settings,
            message_id=message_id,
            body=body,
            reply_all=reply_all,
            from_account=from_account,
            limit=limit_value,
        )
    except ValueError as exc:
        return error_response("INVALID_INPUT", str(exc))
    except SafetyPolicyError as exc:
        return error_response("SAFETY_POLICY_BLOCK", str(exc))
    except MailBridgeError as exc:
        return error_response("THREAD_REPLY_FAILED", str(exc))


def mail_archive_thread(
    message_id: str,
    archive_mailbox: str = "Archive",
    archive_account: str | None = None,
    limit: int | str = 25,
    *,
    bridge: AppleMailBridge | None = None,
    settings: Settings | None = None,
) -> ThreadMutationRecord | ErrorResponse:
    active_settings = settings or load_settings()
    try:
        limit_value = _coerce_int_arg("limit", limit, minimum=1)
        return mail_archive_thread_tool(
            bridge or AppleMailBridge(),
            active_settings,
            message_id=message_id,
            archive_mailbox=archive_mailbox,
            archive_account=archive_account,
            limit=limit_value,
        )
    except ValueError as exc:
        return error_response("INVALID_INPUT", str(exc))
    except SafetyPolicyError as exc:
        return error_response("SAFETY_POLICY_BLOCK", str(exc))
    except MailBridgeError as exc:
        return error_response("THREAD_ARCHIVE_FAILED", str(exc))


def create_server(settings: Settings | None = None, bridge: AppleMailBridge | None = None) -> FastMCP:
    server_settings = settings or load_settings()
    configure_logging(server_settings)
    mail_bridge = bridge or AppleMailBridge()
    mcp = FastMCP(
        "Apple Mail MCP",
        instructions=SERVER_INSTRUCTIONS,
        host=server_settings.host,
        port=server_settings.port,
        log_level=server_settings.log_level,
        json_response=True,
        stateless_http=True,
    )

    @mcp.resource(
        "mail://mailboxes",
        name="mailboxes_snapshot",
        title="Mailboxes",
        description="Current Apple Mail mailboxes.",
        mime_type="application/json",
        annotations=Annotations(audience=["assistant"], priority=0.9),
    )
    def mailboxes_resource() -> str:
        return mailboxes_resource_tool(mail_bridge)

    @mcp.prompt(name="mail_inbox_triage", title="Triage Inbox")
    def mail_inbox_triage_prompt() -> str:
        return mail_inbox_triage_prompt_text()

    @mcp.prompt(name="mail_draft_reply", title="Draft Reply")
    def mail_draft_reply_prompt() -> str:
        return mail_draft_reply_prompt_text()

    @mcp.tool(
        title="Mail Health",
        description="Report the active Apple Mail MCP configuration.",
        annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
        structured_output=True,
    )
    def health() -> HealthResponse:
        return mail_health(server_settings)

    @mcp.tool(
        title="Mail Permission Guide",
        description="Explain how to grant Apple Mail automation permission on macOS.",
        annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
        structured_output=True,
    )
    def mail_permission_guide_registered() -> dict[str, object]:
        return mail_permission_guide()

    @mcp.tool(
        title="Mail Recheck Permissions",
        description="Recheck Mail access after the user changes macOS permissions, and notify the client that Mail resources changed.",
        annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=False),
        structured_output=True,
    )
    async def mail_recheck_permissions_registered(ctx: Context) -> HealthResponse:
        return await mail_recheck_permissions(ctx)

    @mcp.tool(
        title="List Mailboxes",
        description="List Apple Mail mailboxes, optionally filtered by account.",
        annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
        structured_output=True,
    )
    def mail_list_mailboxes_registered(account: str | None = None) -> MailboxListResponse | ErrorResponse:
        return mail_list_mailboxes(account=account, bridge=mail_bridge)

    @mcp.tool(
        title="Search Messages",
        description="Search Apple Mail messages by query with optional mailbox and unread filters.",
        annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
        structured_output=True,
    )
    def mail_search_messages_registered(
        query: str,
        mailbox: str | None = None,
        unread_only: bool = False,
        limit: int | str = 10,
    ) -> MessageSearchResponse | ErrorResponse:
        return mail_search_messages(
            query=query,
            mailbox=mailbox,
            unread_only=unread_only,
            limit=limit,
            bridge=mail_bridge,
            settings=server_settings,
        )

    @mcp.tool(
        title="Get Message",
        description="Fetch a single Apple Mail message by message_id.",
        annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
        structured_output=True,
    )
    def mail_get_message_registered(message_id: str) -> MessageRecord | ErrorResponse:
        return mail_get_message(message_id=message_id, bridge=mail_bridge)

    @mcp.tool(
        title="Get Thread",
        description="Find related messages in the same mailbox thread by normalized subject, anchored on a message_id.",
        annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
        structured_output=True,
    )
    def mail_get_thread_registered(message_id: str, limit: int | str = 25) -> ThreadRecord | ErrorResponse:
        return mail_get_thread(message_id=message_id, limit=limit, bridge=mail_bridge, settings=server_settings)

    @mcp.tool(
        title="Compose Draft",
        description="Create a draft message in Apple Mail without sending it. Optionally specify from_account as an email address or account name to set the sender.",
        annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
        structured_output=True,
    )
    def mail_compose_draft_registered(
        to: list[str],
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        subject: str = "",
        body: str = "",
        attachments: list[str] | None = None,
        from_account: str | None = None,
    ) -> DraftRecord | ErrorResponse:
        return mail_compose_draft(
            to=to,
            cc=cc,
            bcc=bcc,
            subject=subject,
            body=body,
            attachments=attachments,
            from_account=from_account,
            bridge=mail_bridge,
            settings=server_settings,
        )

    @mcp.tool(
        title="Send Message",
        description="Send an email immediately via Apple Mail. Optionally specify from_account as an email address or account name to set the sender.",
        annotations=ToolAnnotations(destructiveHint=True, idempotentHint=False, openWorldHint=True),
        structured_output=True,
    )
    def mail_send_message_registered(
        to: list[str],
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        subject: str = "",
        body: str = "",
        attachments: list[str] | None = None,
        from_account: str | None = None,
    ) -> SendRecord | ErrorResponse:
        return mail_send_message(
            to=to,
            cc=cc,
            bcc=bcc,
            subject=subject,
            body=body,
            attachments=attachments,
            from_account=from_account,
            bridge=mail_bridge,
            settings=server_settings,
        )

    @mcp.tool(
        title="Reply to Message",
        description="Reply to an existing email message. Provide a message_id and body text. Set reply_all=true to reply to all recipients. Optionally specify from_account.",
        annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=True),
        structured_output=True,
    )
    def mail_reply_message_registered(
        message_id: str,
        body: str,
        reply_all: bool = False,
        from_account: str | None = None,
    ) -> ReplyRecord | ErrorResponse:
        return mail_reply_message(
            message_id=message_id,
            body=body,
            reply_all=reply_all,
            from_account=from_account,
            bridge=mail_bridge,
            settings=server_settings,
        )

    @mcp.tool(
        title="Forward Message",
        description="Forward an existing email message to new recipients. Provide a message_id and the to list. Optionally prepend body text and specify from_account.",
        annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=True),
        structured_output=True,
    )
    def mail_forward_message_registered(
        message_id: str,
        to: list[str],
        body: str = "",
        from_account: str | None = None,
    ) -> ForwardRecord | ErrorResponse:
        return mail_forward_message(
            message_id=message_id,
            to=to,
            body=body,
            from_account=from_account,
            bridge=mail_bridge,
            settings=server_settings,
        )

    @mcp.tool(
        title="Mark Message Read/Unread",
        description="Set the read status of an email message. Pass is_read=true to mark as read, is_read=false to mark as unread.",
        annotations=ToolAnnotations(destructiveHint=False, idempotentHint=True, openWorldHint=False),
        structured_output=True,
    )
    def mail_mark_message_registered(
        message_id: str,
        is_read: bool,
    ) -> MarkRecord | ErrorResponse:
        return mail_mark_message(
            message_id=message_id,
            is_read=is_read,
            bridge=mail_bridge,
            settings=server_settings,
        )

    @mcp.tool(
        title="Move Message",
        description="Move an email message to a different mailbox. Optionally specify target_account if the mailbox is in a different account.",
        annotations=ToolAnnotations(destructiveHint=False, idempotentHint=True, openWorldHint=False),
        structured_output=True,
    )
    def mail_move_message_registered(
        message_id: str,
        target_mailbox: str,
        target_account: str | None = None,
    ) -> MoveRecord | ErrorResponse:
        return mail_move_message(
            message_id=message_id,
            target_mailbox=target_mailbox,
            target_account=target_account,
            bridge=mail_bridge,
            settings=server_settings,
        )

    @mcp.tool(
        title="Delete Message",
        description="Delete (trash) an email message by its message_id.",
        annotations=ToolAnnotations(destructiveHint=True, idempotentHint=True, openWorldHint=False),
        structured_output=True,
    )
    def mail_delete_message_registered(
        message_id: str,
    ) -> DeleteRecord | ErrorResponse:
        return mail_delete_message(
            message_id=message_id,
            bridge=mail_bridge,
            settings=server_settings,
        )

    @mcp.tool(
        title="Reply To Latest In Thread",
        description="Find the latest related message in the same mailbox thread and reply to that message.",
        annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=True),
        structured_output=True,
    )
    def mail_reply_latest_in_thread_registered(
        message_id: str,
        body: str,
        reply_all: bool = False,
        from_account: str | None = None,
        limit: int | str = 25,
    ) -> ReplyRecord | ErrorResponse:
        return mail_reply_latest_in_thread(
            message_id=message_id,
            body=body,
            reply_all=reply_all,
            from_account=from_account,
            limit=limit,
            bridge=mail_bridge,
            settings=server_settings,
        )

    @mcp.tool(
        title="Archive Thread",
        description="Move related messages in the same mailbox thread to the target archive mailbox.",
        annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
        structured_output=True,
    )
    def mail_archive_thread_registered(
        message_id: str,
        archive_mailbox: str = "Archive",
        archive_account: str | None = None,
        limit: int | str = 25,
    ) -> ThreadMutationRecord | ErrorResponse:
        return mail_archive_thread(
            message_id=message_id,
            archive_mailbox=archive_mailbox,
            archive_account=archive_account,
            limit=limit,
            bridge=mail_bridge,
            settings=server_settings,
        )

    def _serialize_prompt_messages(messages: list[object]) -> list[dict[str, object]]:
        return [
            {
                "role": getattr(message, "role", "user"),
                "content": message.content.model_dump(mode="json") if hasattr(message.content, "model_dump") else message.content,
            }
            for message in messages
        ]

    @mcp.tool(
        title="Mail List Prompts",
        description="Fallback prompt discovery tool for tool-only MCP clients.",
        annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
        structured_output=True,
    )
    async def mail_list_prompts() -> dict[str, object]:
        prompts = await mcp.list_prompts()
        return {
            "ok": True,
            "prompts": [{"name": prompt.name, "title": prompt.title, "description": prompt.description} for prompt in prompts],
            "count": len(prompts),
        }

    @mcp.tool(
        title="Mail Get Prompt",
        description="Fallback prompt rendering tool for tool-only MCP clients.",
        annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
        structured_output=True,
    )
    async def mail_get_prompt_prompt(name: str, arguments_json: str | None = None) -> dict[str, object]:
        arguments = json.loads(arguments_json) if arguments_json else None
        prompt = await mcp.get_prompt(name, arguments)
        return {"ok": True, "name": name, "messages": _serialize_prompt_messages(prompt.messages), "message_count": len(prompt.messages)}

    @mcp._mcp_server.subscribe_resource()
    async def _mail_subscribe_resource(uri) -> None:
        del uri

    @mcp._mcp_server.unsubscribe_resource()
    async def _mail_unsubscribe_resource(uri) -> None:
        del uri

    return mcp


def main() -> None:
    settings = load_settings()
    server = create_server(settings=settings)
    if settings.transport == "stdio":
        server.run(transport="stdio")
        return
    server.run(transport="streamable-http")
