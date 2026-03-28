from __future__ import annotations

import json
import logging

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import Annotations, ToolAnnotations

from apple_mail_mcp.config import Settings, load_settings
from apple_mail_mcp.mail_bridge import AppleMailBridge, MailBridgeError
from apple_mail_mcp.models import DraftRecord, ErrorResponse, HealthResponse, MailboxListResponse, MessageRecord, MessageSearchResponse, SendRecord, error_response
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
            "compose_draft",
            "send_message",
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
) -> SendRecord:
    ensure_tool_allowed(settings.safety_profile, "mail_send_message")
    result = bridge.send_message(
        to=to,
        cc=cc,
        bcc=bcc,
        subject=subject,
        body=body,
        attachments=attachments,
    )
    LOGGER.info("mail_send_message ok subject=%s recipients=%s", subject, len(to))
    return result


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
        )
    except SafetyPolicyError as exc:
        return error_response("SAFETY_POLICY_BLOCK", str(exc))
    except MailBridgeError as exc:
        return error_response("SEND_FAILED", str(exc))


def create_server(settings: Settings | None = None, bridge: AppleMailBridge | None = None) -> FastMCP:
    server_settings = settings or load_settings()
    configure_logging(server_settings)
    mail_bridge = bridge or AppleMailBridge()
    mcp = FastMCP("Apple Mail MCP", instructions=SERVER_INSTRUCTIONS, json_response=True)

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
        title="Compose Draft",
        description="Create a draft message in Apple Mail without sending it.",
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
    ) -> DraftRecord | ErrorResponse:
        return mail_compose_draft(
            to=to,
            cc=cc,
            bcc=bcc,
            subject=subject,
            body=body,
            attachments=attachments,
            bridge=mail_bridge,
            settings=server_settings,
        )

    @mcp.tool(
        title="Send Message",
        description="Send an email immediately via Apple Mail.",
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
    ) -> SendRecord | ErrorResponse:
        return mail_send_message(
            to=to,
            cc=cc,
            bcc=bcc,
            subject=subject,
            body=body,
            attachments=attachments,
            bridge=mail_bridge,
            settings=server_settings,
        )

    return mcp


def main() -> None:
    settings = load_settings()
    server = create_server(settings=settings)
    if settings.transport == "stdio":
        server.run(transport="stdio")
        return
    server.run(
        transport="streamable-http",
        host=settings.host,
        port=settings.port,
        stateless_http=True,
        json_response=True,
    )
