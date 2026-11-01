from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Annotated, Literal

from mcp.server.mcpserver import Context
from mcp.types import Annotations, InputRequiredResult, PromptMessage, ToolAnnotations
from pydantic import Field

from apple_mail_mcp.config import Settings, load_settings
from apple_mail_mcp.mail_bridge import AppleMailBridge, MailBridgeError, MailSendStatusUnknownError
from apple_mail_mcp.models import (
    DeleteRecord,
    DraftRecord,
    ErrorResponse,
    ForwardRecord,
    HealthResponse,
    MailboxListResponse,
    MarkRecord,
    MessageRecord,
    MessageSearchResponse,
    MessageSummary,
    MoveRecord,
    ReplyRecord,
    SafetyProfile,
    SendRecord,
    ThreadMutationRecord,
    ThreadRecord,
    error_response,
    normalized_thread_subject,
)
from apple_mail_mcp.permissions import SAFETY_ENV_VAR, SafetyPolicyError, ensure_tool_allowed
from apple_mcp_common.discovery import install_search_first_discovery
from apple_mcp_common.runtime import notify_resources_changed, python_log_level, require_loopback_host
from apple_mcp_common.safety import how_to_set, safety_mode_warning
from apple_mcp_common.server import AppleMCPServer

LOGGER = logging.getLogger("apple_mail_mcp")
SERVER_INSTRUCTIONS = (
    "Use this server for Apple Mail on macOS. "
    "Search here when the user wants to inspect mailboxes, search messages, read a specific message, create drafts, or send email. "
    "Prefer list and read tools before drafting or sending."
)


_MESSAGE_ID = "Message ID exactly as returned by mail_search_messages, mail_get_thread or mail_get_message; it encodes the account, mailbox and message."
_ACCOUNT_FILTER = "Mail account name as returned by mail_list_mailboxes. Omit to cover all accounts."
_FROM_ACCOUNT = "Sender: an account email address or account name from mail_list_mailboxes. Omit to use Mail's default account."
_RECIPIENTS = "Recipient email addresses, one per item."
_ATTACHMENTS = (
    "Absolute paths of files to attach. Each must be a regular file under the configured "
    "APPLE_MAIL_MCP_ALLOWED_ATTACHMENT_ROOT; attachments are rejected when no root is configured."
)
_THREAD_LIMIT = "Maximum number of thread messages to consider (1 or more); the thread is matched by normalized subject in the anchor message's mailbox."
_REPLY_ALL = "True to reply to the sender and all other recipients; false (default) replies to the sender only."
_PROMPT_NAME = "Prompt name as returned by mail_list_prompts."
_PROMPT_ARGUMENTS = "Optional prompt arguments as a JSON object string, for example '{\"topic\": \"invoices\"}'."


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(level=python_log_level(settings.log_level))


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
        safety_mode_warning=safety_mode_warning(SAFETY_ENV_VAR, settings.safety_profile.value),
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
    await notify_resources_changed(ctx)
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
    account: str | None = None,
) -> MessageSearchResponse:
    bounded_limit = max(1, min(limit or settings.default_search_limit, 100))
    results = bridge.search_messages(
        query=query,
        mailbox=mailbox,
        unread_only=unread_only,
        limit=bounded_limit,
        account=account or None,
    )
    return MessageSearchResponse(results=results, count=len(results))


def mail_get_message_tool(bridge: AppleMailBridge, message_id: str) -> MessageRecord:
    return bridge.get_message(message_id)


def _validate_attachments(attachments: list[str] | None, allowed_root: Path | None) -> list[str] | None:
    if not attachments:
        return attachments
    if allowed_root is None:
        raise ValueError("Attachments are disabled; configure APPLE_MAIL_MCP_ALLOWED_ATTACHMENT_ROOT to enable them")

    try:
        resolved_root = allowed_root.resolve(strict=True)
    except OSError as exc:
        raise ValueError("The configured attachment root does not exist or cannot be accessed") from exc
    if not resolved_root.is_dir():
        raise ValueError("The configured attachment root must be a directory")

    validated: list[str] = []
    for attachment in attachments:
        if "\x1d" in attachment or "\x00" in attachment:
            raise ValueError("Attachment paths must not contain control separators")
        try:
            resolved_attachment = Path(attachment).expanduser().resolve(strict=True)
            resolved_attachment.relative_to(resolved_root)
        except (OSError, ValueError) as exc:
            raise ValueError(f"Attachment is not a file beneath the allowed attachment root: {attachment}") from exc
        if not resolved_attachment.is_file():
            raise ValueError(f"Attachment is not a regular file: {attachment}")
        if "\x1d" in str(resolved_attachment) or "\x00" in str(resolved_attachment):
            raise ValueError("Attachment paths must not contain control separators")
        validated.append(str(resolved_attachment))
    return validated


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
    attachments = _validate_attachments(attachments, settings.allowed_attachment_root)
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
    attachments = _validate_attachments(attachments, settings.allowed_attachment_root)
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
    # A reply goes to whoever wrote the message, and reply_all to everyone on
    # it, so like a forward it is only sent directly in full_access. Below that
    # it is left in Mail as a draft, which keeps safe_manage from sending mail.
    send = settings.safety_profile == SafetyProfile.FULL_ACCESS
    result = bridge.reply_message(
        message_id=message_id,
        body=body,
        reply_all=reply_all,
        from_account=from_account,
        send=send,
    )
    if not result.sent:
        result.note = (
            f"Reply saved as a draft in Mail and NOT sent, because {SAFETY_ENV_VAR} is "
            f"'{settings.safety_profile.value}'. Ask the user to review and send it in Mail. "
            f"To send replies directly, {how_to_set(SAFETY_ENV_VAR, SafetyProfile.FULL_ACCESS.value)}."
        )
    LOGGER.info("mail_reply_message ok message_id=%s reply_all=%s sent=%s", message_id, reply_all, result.sent)
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
    # A forward can reach any address, so it is only sent directly in
    # full_access. Below that it is left in Mail as a draft for the user to
    # review, which keeps safe_manage from sending mail to new recipients.
    send = settings.safety_profile == SafetyProfile.FULL_ACCESS
    result = bridge.forward_message(
        message_id=message_id,
        to=to,
        body=body,
        from_account=from_account,
        send=send,
    )
    if not result.sent:
        result.note = (
            f"Forward saved as a draft in Mail and NOT sent, because {SAFETY_ENV_VAR} is "
            f"'{settings.safety_profile.value}'. Ask the user to review and send it in Mail. "
            f"To send forwards directly, {how_to_set(SAFETY_ENV_VAR, SafetyProfile.FULL_ACCESS.value)}."
        )
    LOGGER.info("mail_forward_message ok message_id=%s recipients=%s sent=%s", message_id, len(to), result.sent)
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
    # A missing subject does not establish a thread. Sender-only matching
    # would let archive/reply operate on unrelated messages from that sender.
    candidates = []
    if normalized_subject:
        candidates = bridge.search_messages(
            query=normalized_subject,
            mailbox=anchor.mailbox,
            unread_only=False,
            limit=max(25, min(limit * 4, 100)),
            # Mailbox names repeat across accounts ("Inbox"); without this a
            # same-subject message in another account could join the thread,
            # and archive/reply-latest would act on it.
            account=anchor.account or None,
        )
    matched: list[MessageSummary] = []
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
    account: str | None = None,
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
            account=account,
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
        return error_response("SAFETY_POLICY_BLOCK", str(exc), exc.suggestion)
    except ValueError as exc:
        return error_response("INVALID_INPUT", str(exc))
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
        return error_response("SAFETY_POLICY_BLOCK", str(exc), exc.suggestion)
    except ValueError as exc:
        return error_response("INVALID_INPUT", str(exc))
    except MailSendStatusUnknownError as exc:
        return error_response("SEND_STATUS_UNKNOWN", str(exc), exc.suggestion)
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
        return error_response("SAFETY_POLICY_BLOCK", str(exc), exc.suggestion)
    except MailSendStatusUnknownError as exc:
        return error_response("SEND_STATUS_UNKNOWN", str(exc), exc.suggestion)
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
        return error_response("SAFETY_POLICY_BLOCK", str(exc), exc.suggestion)
    except MailSendStatusUnknownError as exc:
        return error_response("SEND_STATUS_UNKNOWN", str(exc), exc.suggestion)
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
        return error_response("SAFETY_POLICY_BLOCK", str(exc), exc.suggestion)
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
        return error_response("SAFETY_POLICY_BLOCK", str(exc), exc.suggestion)
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
        return error_response("SAFETY_POLICY_BLOCK", str(exc), exc.suggestion)
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
        return error_response("SAFETY_POLICY_BLOCK", str(exc), exc.suggestion)
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
        return error_response("SAFETY_POLICY_BLOCK", str(exc), exc.suggestion)
    except MailSendStatusUnknownError as exc:
        return error_response("SEND_STATUS_UNKNOWN", str(exc), exc.suggestion)
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
        return error_response("SAFETY_POLICY_BLOCK", str(exc), exc.suggestion)
    except MailBridgeError as exc:
        return error_response("THREAD_ARCHIVE_FAILED", str(exc))


_McpLogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
_MCP_LOG_LEVELS: dict[str, _McpLogLevel] = {
    "DEBUG": "DEBUG",
    "INFO": "INFO",
    "WARN": "WARNING",
    "WARNING": "WARNING",
    "ERROR": "ERROR",
    "CRITICAL": "CRITICAL",
}


def _mcp_log_level(value: str) -> _McpLogLevel:
    """Map a LOG_LEVEL setting onto a level the MCP SDK accepts; unknown values fall back to INFO."""
    return _MCP_LOG_LEVELS.get(value.strip().upper(), "INFO")


def create_server(settings: Settings | None = None, bridge: AppleMailBridge | None = None) -> AppleMCPServer:
    server_settings = settings or load_settings()
    mail_bridge = bridge or AppleMailBridge(script_timeout=server_settings.script_timeout_seconds)
    mcp = AppleMCPServer(
        "Apple Mail MCP",
        instructions=SERVER_INSTRUCTIONS,
        version=server_settings.version,
        log_level=_mcp_log_level(server_settings.log_level),
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
        name="mail_health",
        title="Mail Health",
        description="Report the active Apple Mail MCP configuration.",
        annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
        structured_output=True,
    )
    def health() -> HealthResponse:
        return mail_health(server_settings)

    @mcp.tool(
        name="mail_permission_guide",
        title="Mail Permission Guide",
        description="Explain how to grant Apple Mail automation permission on macOS.",
        annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
        structured_output=True,
    )
    def mail_permission_guide_registered() -> dict[str, object]:
        return mail_permission_guide()

    @mcp.tool(
        name="mail_recheck_permissions",
        title="Mail Recheck Permissions",
        description="Recheck Mail access after the user changes macOS permissions, and notify the client that Mail resources changed.",
        annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=False, open_world_hint=False),
        structured_output=True,
    )
    async def mail_recheck_permissions_registered(ctx: Context) -> HealthResponse:
        return await mail_recheck_permissions(ctx)

    @mcp.tool(
        name="mail_list_mailboxes",
        title="List Mailboxes",
        description="List Apple Mail mailboxes, optionally filtered by account.",
        annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
        structured_output=True,
    )
    def mail_list_mailboxes_registered(account: Annotated[str | None, Field(description=_ACCOUNT_FILTER)] = None) -> MailboxListResponse | ErrorResponse:
        return mail_list_mailboxes(account=account, bridge=mail_bridge)

    @mcp.tool(
        name="mail_search_messages",
        title="Search Mail",
        description=(
            "Search Apple Mail messages by query with optional account, mailbox and unread filters. "
            "Without account, accounts are searched in Mail's order and the limit can be filled by the first one; "
            "pass account (as returned by mail_list_mailboxes) to search a specific account."
        ),
        annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
        structured_output=True,
    )
    def mail_search_messages_registered(
        query: Annotated[str, Field(description='Text matched against message subject or sender (case-insensitive contains). Use "*" to match every message.')],
        mailbox: Annotated[str | None, Field(description='Mailbox name to search, such as "INBOX" or "Archive", as returned by mail_list_mailboxes. Omit to search all mailboxes.')] = None,
        unread_only: Annotated[bool, Field(description="True to return only unread messages.")] = False,
        limit: Annotated[int | str, Field(description="Maximum number of messages to return, 1 to 100.")] = 10,
        account: Annotated[str | None, Field(description=_ACCOUNT_FILTER)] = None,
    ) -> MessageSearchResponse | ErrorResponse:
        return mail_search_messages(
            query=query,
            mailbox=mailbox,
            unread_only=unread_only,
            limit=limit,
            account=account,
            bridge=mail_bridge,
            settings=server_settings,
        )

    @mcp.tool(
        name="mail_get_message",
        title="Get Email",
        description="Fetch a single Apple Mail message by message_id.",
        annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
        structured_output=True,
    )
    def mail_get_message_registered(message_id: Annotated[str, Field(description=_MESSAGE_ID)]) -> MessageRecord | ErrorResponse:
        return mail_get_message(message_id=message_id, bridge=mail_bridge)

    @mcp.tool(
        name="mail_get_thread",
        title="Get Thread",
        description="Find related messages in the same mailbox thread by normalized subject, anchored on a message_id.",
        annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
        structured_output=True,
    )
    def mail_get_thread_registered(
        message_id: Annotated[str, Field(description=_MESSAGE_ID)],
        limit: Annotated[int | str, Field(description=_THREAD_LIMIT)] = 25,
    ) -> ThreadRecord | ErrorResponse:
        return mail_get_thread(message_id=message_id, limit=limit, bridge=mail_bridge, settings=server_settings)

    @mcp.tool(
        name="mail_compose_draft",
        title="Compose Draft",
        description="Create a draft message in Apple Mail without sending it. Optionally specify from_account as an email address or account name to set the sender.",
        annotations=ToolAnnotations(destructive_hint=False, idempotent_hint=False, open_world_hint=False),
        structured_output=True,
    )
    def mail_compose_draft_registered(
        to: Annotated[list[str], Field(description=_RECIPIENTS)],
        cc: Annotated[list[str] | None, Field(description="Carbon-copy email addresses, one per item.")] = None,
        bcc: Annotated[list[str] | None, Field(description="Blind carbon-copy email addresses, one per item.")] = None,
        subject: Annotated[str, Field(description="Subject line.")] = "",
        body: Annotated[str, Field(description="Plain-text message body.")] = "",
        attachments: Annotated[list[str] | None, Field(description=_ATTACHMENTS)] = None,
        from_account: Annotated[str | None, Field(description=_FROM_ACCOUNT)] = None,
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
        name="mail_send_message",
        title="Send Email",
        description="Send an email immediately via Apple Mail. Optionally specify from_account as an email address or account name to set the sender.",
        annotations=ToolAnnotations(destructive_hint=True, idempotent_hint=False, open_world_hint=True),
        structured_output=True,
    )
    def mail_send_message_registered(
        to: Annotated[list[str], Field(description=_RECIPIENTS)],
        cc: Annotated[list[str] | None, Field(description="Carbon-copy email addresses, one per item.")] = None,
        bcc: Annotated[list[str] | None, Field(description="Blind carbon-copy email addresses, one per item.")] = None,
        subject: Annotated[str, Field(description="Subject line.")] = "",
        body: Annotated[str, Field(description="Plain-text message body.")] = "",
        attachments: Annotated[list[str] | None, Field(description=_ATTACHMENTS)] = None,
        from_account: Annotated[str | None, Field(description=_FROM_ACCOUNT)] = None,
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
        name="mail_reply_message",
        title="Reply to Message",
        description="Reply to an existing email message. Provide a message_id and body text. Set reply_all=true to reply to all recipients. Optionally specify from_account. In full_access the reply is sent; in safe_manage it is saved as an unsent draft in Mail for the user to review (check `sent` and `note` in the result).",
        annotations=ToolAnnotations(destructive_hint=True, idempotent_hint=False, open_world_hint=True),
        structured_output=True,
    )
    def mail_reply_message_registered(
        message_id: Annotated[str, Field(description=_MESSAGE_ID + " This is the message being replied to.")],
        body: Annotated[str, Field(description="Plain-text reply body, placed above the quoted original.")],
        reply_all: Annotated[bool, Field(description=_REPLY_ALL)] = False,
        from_account: Annotated[str | None, Field(description=_FROM_ACCOUNT)] = None,
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
        name="mail_forward_message",
        title="Forward Message",
        description="Forward an existing email message to new recipients. Provide a message_id and the to list. Optionally prepend body text and specify from_account. In full_access the forward is sent; in safe_manage it is saved as an unsent draft in Mail for the user to review (check `sent` and `note` in the result).",
        annotations=ToolAnnotations(destructive_hint=True, idempotent_hint=False, open_world_hint=True),
        structured_output=True,
    )
    def mail_forward_message_registered(
        message_id: Annotated[str, Field(description=_MESSAGE_ID + " This is the message being forwarded.")],
        to: Annotated[list[str], Field(description=_RECIPIENTS)],
        body: Annotated[str, Field(description="Optional plain-text note placed above the forwarded message.")] = "",
        from_account: Annotated[str | None, Field(description=_FROM_ACCOUNT)] = None,
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
        name="mail_mark_message",
        title="Mark Message Read/Unread",
        description="Set the read status of an email message. Pass is_read=true to mark as read, is_read=false to mark as unread.",
        annotations=ToolAnnotations(destructive_hint=True, idempotent_hint=True, open_world_hint=False),
        structured_output=True,
    )
    def mail_mark_message_registered(
        message_id: Annotated[str, Field(description=_MESSAGE_ID)],
        is_read: Annotated[bool, Field(description="True to mark the message read, false to mark it unread.")],
    ) -> MarkRecord | ErrorResponse:
        return mail_mark_message(
            message_id=message_id,
            is_read=is_read,
            bridge=mail_bridge,
            settings=server_settings,
        )

    @mcp.tool(
        name="mail_move_message",
        title="Move Message",
        description="Move an email message to a different mailbox. Optionally specify target_account if the mailbox is in a different account.",
        annotations=ToolAnnotations(destructive_hint=True, idempotent_hint=True, open_world_hint=False),
        structured_output=True,
    )
    def mail_move_message_registered(
        message_id: Annotated[str, Field(description=_MESSAGE_ID)],
        target_mailbox: Annotated[str, Field(description="Exact name of the destination mailbox, as returned by mail_list_mailboxes.")],
        target_account: Annotated[str | None, Field(description="Account that owns target_mailbox. Omit to use the message's own account.")] = None,
    ) -> MoveRecord | ErrorResponse:
        return mail_move_message(
            message_id=message_id,
            target_mailbox=target_mailbox,
            target_account=target_account,
            bridge=mail_bridge,
            settings=server_settings,
        )

    @mcp.tool(
        name="mail_delete_message",
        title="Delete Message",
        description="Delete (trash) an email message by its message_id.",
        annotations=ToolAnnotations(destructive_hint=True, idempotent_hint=True, open_world_hint=False),
        structured_output=True,
    )
    def mail_delete_message_registered(
        message_id: Annotated[str, Field(description=_MESSAGE_ID + " The message is moved to the account's Trash.")],
    ) -> DeleteRecord | ErrorResponse:
        return mail_delete_message(
            message_id=message_id,
            bridge=mail_bridge,
            settings=server_settings,
        )

    @mcp.tool(
        name="mail_reply_latest_in_thread",
        title="Reply To Latest In Thread",
        description="Find the latest related message in the same mailbox thread and reply to that message. In full_access the reply is sent; in safe_manage it is saved as an unsent draft in Mail for the user to review (check `sent` and `note` in the result).",
        annotations=ToolAnnotations(destructive_hint=True, idempotent_hint=False, open_world_hint=True),
        structured_output=True,
    )
    def mail_reply_latest_in_thread_registered(
        message_id: Annotated[str, Field(description=_MESSAGE_ID + " Any message in the thread; the reply goes to the latest one.")],
        body: Annotated[str, Field(description="Plain-text reply body, placed above the quoted original.")],
        reply_all: Annotated[bool, Field(description=_REPLY_ALL)] = False,
        from_account: Annotated[str | None, Field(description=_FROM_ACCOUNT)] = None,
        limit: Annotated[int | str, Field(description=_THREAD_LIMIT)] = 25,
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
        name="mail_archive_thread",
        title="Archive Thread",
        description="Move related messages in the same mailbox thread to the target archive mailbox.",
        annotations=ToolAnnotations(destructive_hint=True, idempotent_hint=False, open_world_hint=False),
        structured_output=True,
    )
    def mail_archive_thread_registered(
        message_id: Annotated[str, Field(description=_MESSAGE_ID + " Any message in the thread to archive.")],
        archive_mailbox: Annotated[str, Field(description='Exact name of the destination mailbox (default "Archive"), as returned by mail_list_mailboxes.')] = "Archive",
        archive_account: Annotated[str | None, Field(description="Account that owns archive_mailbox. Omit to use each message's own account.")] = None,
        limit: Annotated[int | str, Field(description="Maximum number of thread messages to move (1 or more); the thread is matched by normalized subject in the anchor message's mailbox.")] = 25,
    ) -> ThreadMutationRecord | ErrorResponse:
        return mail_archive_thread(
            message_id=message_id,
            archive_mailbox=archive_mailbox,
            archive_account=archive_account,
            limit=limit,
            bridge=mail_bridge,
            settings=server_settings,
        )

    def _serialize_prompt_messages(messages: list[PromptMessage]) -> list[dict[str, object]]:
        return [
            {
                "role": getattr(message, "role", "user"),
                "content": message.content.model_dump(mode="json") if hasattr(message.content, "model_dump") else message.content,
            }
            for message in messages
        ]

    @mcp.tool(
        name="mail_list_prompts",
        title="Mail List Prompts",
        description="Fallback prompt discovery tool for tool-only MCP clients.",
        annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
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
        name="mail_get_prompt",
        title="Mail Get Prompt",
        description="Fallback prompt rendering tool for tool-only MCP clients.",
        annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
        structured_output=True,
    )
    async def mail_get_prompt_prompt(
        name: Annotated[str, Field(description=_PROMPT_NAME)],
        arguments_json: Annotated[str | None, Field(description=_PROMPT_ARGUMENTS)] = None,
    ) -> dict[str, object]:
        arguments = json.loads(arguments_json) if arguments_json else None
        prompt = await mcp.get_prompt(name, arguments)
        if isinstance(prompt, InputRequiredResult):
            return {"ok": False, "name": name, "error": {"error_code": "PROMPT_INPUT_REQUIRED", "message": f"Prompt '{name}' needs client input before it can render."}}
        return {"ok": True, "name": name, "messages": _serialize_prompt_messages(prompt.messages), "message_count": len(prompt.messages)}

    # scripts/generate_tool_search_artifacts.py reads this back from the server instance.
    mcp._tool_discovery = install_search_first_discovery(mcp, server_name="Apple Mail MCP", domain="mail")  # ty: ignore[unresolved-attribute]

    return mcp


def main() -> None:
    settings = load_settings()
    configure_logging(settings)
    server = create_server(settings=settings)
    if settings.transport == "streamable-http":
        server.run(
            transport="streamable-http",
            host=require_loopback_host(settings.host),
            port=settings.port,
            json_response=True,
            stateless_http=False,
        )
        return
    server.run(transport="stdio")
