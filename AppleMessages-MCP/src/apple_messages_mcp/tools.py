from __future__ import annotations

import json
import os
from typing import Annotated, Literal

from mcp.server.mcpserver import Context
from mcp.types import Annotations, InputRequiredResult, PromptMessage, ToolAnnotations
from pydantic import Field

from apple_mcp_common.discovery import install_search_first_discovery
from apple_mcp_common.runtime import notify_resources_changed, require_loopback_host
from apple_mcp_common.safety import safety_mode_warning
from apple_mcp_common.server import AppleMCPServer
from apple_messages_mcp.config import load_settings
from apple_messages_mcp.messages_automation_bridge import (
    MessagesAutomationBridge,
    MessagesAutomationBridgeError,
    normalize_service_name,
)
from apple_messages_mcp.messages_db_bridge import MessagesDBBridge, MessagesDBBridgeError
from apple_messages_mcp.models import (
    AttachmentListResponse,
    ConversationListResponse,
    ConversationResponse,
    ErrorResponse,
    HealthResponse,
    MessageResponse,
    MessagesCapabilities,
    MessageSearchResponse,
    SendResponse,
    ToolError,
)
from apple_messages_mcp.permissions import SAFETY_ENV_VAR, SafetyError, ensure_action_allowed

SERVER_INSTRUCTIONS = (
    "Use this server for Apple Messages on macOS. "
    "Search here when the user wants to inspect message history, summarize conversations, search what someone said, or send and reply through Messages. "
    "History features require Full Disk Access, while send features require Messages automation permission."
)

_CHAT_ID = "Conversation id: the chat_id returned by messages_list_conversations or messages_search_messages. Pass it unchanged."
_MESSAGE_ID = "Message id: the message_id returned by messages_get_conversation or messages_search_messages."
_LIMIT = "Maximum number of results to return; must be 1 or more."
_OFFSET = "Number of results to skip, for paging; 0 or more."
_RECIPIENT = (
    "Who to send to: a phone number (E.164 such as +15551234567 is safest) or an email address registered with iMessage. "
    "Resolve names to an address first with contacts_resolve_message_recipient."
)
_SERVICE_NAME = (
    "Service to send over: iMessage, SMS or RCS (case-insensitive). Omit to send as iMessage. "
    "SMS and RCS go through the paired iPhone and need Text Message Forwarding enabled for this Mac."
)
_ISO_BOUND = "ISO 8601 datetime, e.g. 2026-04-07T18:00:00-05:00; without an offset it is read as local time."

mcp = AppleMCPServer("Apple Messages MCP", instructions=SERVER_INSTRUCTIONS, version=load_settings().version)


_AUTOMATION_STATUS_BY_ERROR_CODE: dict[str, Literal["not_probed", "unknown", "denied"]] = {
    "NOT_PROBED": "not_probed",
    "AUTHORIZATION_UNKNOWN": "unknown",
    "PERMISSION_DENIED": "denied",
}



def _db_bridge() -> MessagesDBBridge:
    return MessagesDBBridge(load_settings().db_path)


def _automation_bridge() -> MessagesAutomationBridge:
    return MessagesAutomationBridge()


def _error_response(error_code: str, message: str, suggestion: str | None = None) -> ErrorResponse:
    return ErrorResponse(error=ToolError(error_code=error_code, message=message, suggestion=suggestion))


def _capabilities() -> MessagesCapabilities:
    history_access, _history_error, automation_access, _automation_error = _access_diagnostics()
    return MessagesCapabilities(
        can_read_history=history_access,
        can_send_messages=automation_access,
        can_reply_in_existing_chat=history_access and automation_access,
    )


def _access_diagnostics() -> tuple[bool, MessagesDBBridgeError | None, bool, MessagesAutomationBridgeError | None]:
    db = _db_bridge()
    automation = _automation_bridge()
    history_access, history_error = db.history_access_diagnostic()
    automation_access, automation_error = automation.automation_access_diagnostic()
    return history_access, history_error, automation_access, automation_error


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


@mcp.resource(
    "messages://conversations/recent",
    name="messages_recent",
    title="Recent Conversations",
    description="Recent Apple Messages conversations when history access is available.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.9),
)
def messages_recent_resource() -> str:
    try:
        conversations = _db_bridge().list_conversations(limit=20)
        return _resource_json({"conversations": [item.model_dump() for item in conversations], "count": len(conversations)})
    except MessagesDBBridgeError as exc:
        return _resource_json({"ok": False, "error_code": exc.error_code, "message": exc.message, "suggestion": exc.suggestion})


@mcp.resource(
    "messages://conversation/{chat_id}",
    name="messages_conversation",
    title="Conversation Snapshot",
    description="A paginated Apple Messages conversation snapshot.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.8),
)
def messages_conversation_resource(chat_id: str) -> str:
    try:
        conversation = _db_bridge().get_conversation(chat_id, limit=50, offset=0)
        return _resource_json(conversation.model_dump())
    except MessagesDBBridgeError as exc:
        return _resource_json({"ok": False, "error_code": exc.error_code, "message": exc.message, "suggestion": exc.suggestion})


@mcp.resource(
    "messages://unread",
    name="messages_unread",
    title="Unread Conversations",
    description="Unread Apple Messages conversations when history access is available.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.8),
)
def messages_unread_resource() -> str:
    try:
        conversations = _db_bridge().list_conversations(limit=50, unread_only=True)
        return _resource_json({"conversations": [item.model_dump() for item in conversations], "count": len(conversations)})
    except MessagesDBBridgeError as exc:
        return _resource_json({"ok": False, "error_code": exc.error_code, "message": exc.message, "suggestion": exc.suggestion})


@mcp.prompt(name="messages_triage_unread", title="Triage Unread")
def messages_triage_unread_prompt() -> str:
    return "Review unread Apple Messages conversations, summarize what needs attention, and suggest the next replies or follow-ups."


@mcp.prompt(name="messages_summarize_thread", title="Summarize Thread")
def messages_summarize_thread_prompt() -> str:
    return "Inspect an Apple Messages conversation, summarize the thread, and highlight open questions, commitments, or deadlines."


@mcp.prompt(name="messages_draft_reply", title="Draft Reply")
def messages_draft_reply_prompt() -> str:
    return "Search Apple Messages for the relevant conversation, read the latest context, and draft a concise reply before sending."


@mcp.tool(
    title="Messages Health",
    description="Report Messages server configuration and capability status.",
    annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
    structured_output=True,
)
def messages_health() -> HealthResponse:
    settings = load_settings()
    history_access, history_error, automation_access, automation_error = _access_diagnostics()
    caps = MessagesCapabilities(
        can_read_history=history_access,
        can_send_messages=automation_access,
        can_reply_in_existing_chat=history_access and automation_access,
    )
    return HealthResponse(
        server_name=settings.server_name,
        version=settings.version,
        safety_mode=settings.safety_mode,
        safety_mode_warning=safety_mode_warning(SAFETY_ENV_VAR, settings.safety_mode),
        capabilities=caps,
        history_access=history_access,
        automation_access=automation_access,
        automation_access_status=("authorized" if automation_access else _AUTOMATION_STATUS_BY_ERROR_CODE.get(
            automation_error.error_code if automation_error is not None else "", "failed"
        )),
        automation_access_error_code=automation_error.error_code if automation_error is not None else None,
        history_access_error=history_error.message if history_error is not None else None,
        history_access_suggestion=history_error.suggestion if history_error is not None else None,
        automation_access_error=automation_error.message if automation_error is not None else None,
        automation_access_suggestion=automation_error.suggestion if automation_error is not None else None,
        transport=settings.transport,
    )


@mcp.tool(
    title="Messages Permission Guide",
    description="Explain how to grant Apple Messages permissions on macOS.",
    annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
    structured_output=True,
)
def messages_permission_guide() -> dict[str, object]:
    return {
        "ok": True,
        "domain": "messages",
        "can_prompt_in_app": True,
        "requires_manual_system_settings": True,
        "steps": [
            "Call a Messages send tool to trigger the Automation prompt for Messages.app.",
            "Approve Automation access when macOS prompts.",
            "Grant Full Disk Access manually in System Settings > Privacy & Security > Full Disk Access for Messages history access.",
        ],
        "notes": [
            "Messages send access and history access are separate permissions.",
            "Full Disk Access cannot be requested programmatically.",
        ],
    }


@mcp.tool(
    title="Messages Recheck Permissions",
    description="Recheck Messages access after the user changes macOS permissions, and notify the client that Messages resources changed.",
    annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=False, open_world_hint=False),
    structured_output=True,
)
async def messages_recheck_permissions(ctx: Context) -> HealthResponse:
    await ctx.report_progress(25, 100, "Rechecking Messages access")
    response = messages_health()
    await notify_resources_changed(ctx)
    await ctx.report_progress(100, 100, "Done")
    return response


@mcp.tool(
    title="List Conversations",
    description="List recent Apple Messages conversations.",
    annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
    structured_output=True,
)
def messages_list_conversations(
    limit: Annotated[int | str, Field(description=_LIMIT)] = 25,
    offset: Annotated[int | str, Field(description=_OFFSET)] = 0,
    unread_only: Annotated[bool, Field(description="Only return conversations that have unread incoming messages.")] = False,
) -> ConversationListResponse | ErrorResponse:
    try:
        ensure_action_allowed("messages_list_conversations")
        limit_value = _coerce_int_arg("limit", limit, minimum=1)
        offset_value = _coerce_int_arg("offset", offset, minimum=0)
        conversations = _db_bridge().list_conversations(limit=limit_value, offset=offset_value, unread_only=unread_only)
        return ConversationListResponse(conversations=conversations, count=len(conversations))
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except MessagesDBBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except ValueError as exc:
        return _error_response("INVALID_INPUT", str(exc), "Provide a positive limit and a non-negative offset.")


@mcp.tool(
    title="Get Conversation",
    description="Fetch a single Apple Messages conversation with paginated messages.",
    annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
    structured_output=True,
)
def messages_get_conversation(
    chat_id: Annotated[str, Field(description=_CHAT_ID)],
    limit: Annotated[int | str, Field(description="Maximum number of the latest messages to select; must be 1 or more. The selected page is returned oldest first, so the last item is the most recent.")] = 50,
    offset: Annotated[int | str, Field(description="Number of newest messages to skip, for paging back through history; 0 or more.")] = 0,
) -> ConversationResponse | ErrorResponse:
    try:
        ensure_action_allowed("messages_get_conversation")
        limit_value = _coerce_int_arg("limit", limit, minimum=1)
        offset_value = _coerce_int_arg("offset", offset, minimum=0)
        conversation = _db_bridge().get_conversation(chat_id, limit=limit_value, offset=offset_value)
        return ConversationResponse(conversation=conversation)
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except MessagesDBBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except ValueError as exc:
        return _error_response("INVALID_INPUT", str(exc), "Provide a positive limit and a non-negative offset.")


@mcp.tool(
    title="Search Messages",
    description="Search Apple Messages text history.",
    annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
    structured_output=True,
)
def messages_search_messages(
    query: Annotated[str, Field(description="Text to find in message bodies and subjects (case-insensitive substring); must not be empty.")],
    chat_id: Annotated[str | None, Field(description="Only search this conversation. " + _CHAT_ID)] = None,
    sender: Annotated[
        str | None,
        Field(description="Only messages from this sender handle, matched exactly as stored (e.g. +15551234567 or person@example.com)."),
    ] = None,
    start_iso: Annotated[str | None, Field(description="Only messages sent at or after this time. " + _ISO_BOUND)] = None,
    end_iso: Annotated[str | None, Field(description="Only messages sent at or before this time. " + _ISO_BOUND)] = None,
    limit: Annotated[int | str, Field(description=_LIMIT)] = 50,
    offset: Annotated[int | str, Field(description=_OFFSET)] = 0,
) -> MessageSearchResponse | ErrorResponse:
    try:
        ensure_action_allowed("messages_search_messages")
        if not query.strip():
            raise ValueError("query must not be empty")
        limit_value = _coerce_int_arg("limit", limit, minimum=1)
        offset_value = _coerce_int_arg("offset", offset, minimum=0)
        results = _db_bridge().search_messages(
            query=query,
            chat_id=chat_id,
            sender=sender,
            start_iso=start_iso,
            end_iso=end_iso,
            limit=limit_value,
            offset=offset_value,
        )
        return MessageSearchResponse(messages=results, count=len(results))
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except MessagesDBBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except ValueError as exc:
        return _error_response("INVALID_INPUT", str(exc), "Provide a non-empty search query, a positive limit, and a non-negative offset.")


@mcp.tool(
    title="Get Message",
    description="Fetch a single Apple Messages message by message_id.",
    annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
    structured_output=True,
)
def messages_get_message(message_id: Annotated[str, Field(description=_MESSAGE_ID)]) -> MessageResponse | ErrorResponse:
    try:
        ensure_action_allowed("messages_get_message")
        message = _db_bridge().get_message(message_id)
        return MessageResponse(message=message)
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except MessagesDBBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="List Message Attachments",
    description="List Apple Messages attachments by chat or message.",
    annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
    structured_output=True,
)
def messages_list_attachments(
    chat_id: Annotated[str | None, Field(description="Only attachments in this conversation. " + _CHAT_ID)] = None,
    message_id: Annotated[str | None, Field(description="Only attachments of this message. " + _MESSAGE_ID)] = None,
    limit: Annotated[int | str, Field(description=_LIMIT)] = 50,
    offset: Annotated[int | str, Field(description=_OFFSET)] = 0,
) -> AttachmentListResponse | ErrorResponse:
    try:
        ensure_action_allowed("messages_list_attachments")
        limit_value = _coerce_int_arg("limit", limit, minimum=1)
        offset_value = _coerce_int_arg("offset", offset, minimum=0)
        attachments = _db_bridge().list_attachments(chat_id=chat_id, message_id=message_id, limit=limit_value, offset=offset_value)
        return AttachmentListResponse(attachments=attachments, count=len(attachments))
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except MessagesDBBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except ValueError as exc:
        return _error_response("INVALID_INPUT", str(exc), "Provide a positive limit and a non-negative offset.")


@mcp.tool(
    title="Send Message",
    description=(
        "Send a new message through Messages.app. Sends as iMessage unless service_name is set: "
        "SMS or RCS go through the iPhone's carrier and need Text Message Forwarding enabled for this Mac."
    ),
    annotations=ToolAnnotations(destructive_hint=True, idempotent_hint=False, open_world_hint=True),
    structured_output=True,
)
def messages_send_message(
    recipient: Annotated[str, Field(description=_RECIPIENT)],
    text: Annotated[str, Field(description="Message text to send; must not be empty.")],
    service_name: Annotated[str | None, Field(description=_SERVICE_NAME)] = None,
) -> SendResponse | ErrorResponse:
    try:
        ensure_action_allowed("messages_send_message")
        result = _automation_bridge().send_message(recipient=recipient, text=text, service_name=service_name)
        return SendResponse(**result)
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except MessagesAutomationBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Reply In Conversation",
    description=(
        "Reply to an Apple Messages conversation using its chat_id. Supports both one-to-one and group chats. "
        "One-to-one replies use the service of the thread's latest message (SMS/RCS threads stay SMS/RCS) unless service_name is set. "
        "Group replies always use the group's existing service; service_name is rejected for groups unless it matches."
    ),
    annotations=ToolAnnotations(destructive_hint=True, idempotent_hint=False, open_world_hint=True),
    structured_output=True,
)
def messages_reply_in_conversation(
    chat_id: Annotated[str, Field(description=_CHAT_ID)],
    text: Annotated[str, Field(description="Reply text to send; must not be empty.")],
    service_name: Annotated[
        str | None,
        Field(
            description=(
                "iMessage, SMS or RCS (case-insensitive). Omit to keep the thread's current service. "
                "Group chats always reply over their existing service, so a different value is rejected."
            )
        ),
    ] = None,
) -> SendResponse | ErrorResponse:
    try:
        ensure_action_allowed("messages_reply_in_conversation")
        participants = _db_bridge().participant_addresses_for_chat(chat_id)
        if len(participants) == 1:
            result = _automation_bridge().send_message(
                recipient=participants[0],
                text=text,
                service_name=service_name,
                services=_thread_service_preference(_db_bridge().latest_service_for_chat(chat_id)),
            )
        elif len(participants) > 1:
            _ensure_group_service_matches(chat_id, service_name)
            result = _automation_bridge().send_to_group(chat_id=chat_id, text=text)
        else:
            return _error_response(
                "EMPTY_CONVERSATION",
                "Could not determine participants for this conversation.",
                "Use messages_send_message with an explicit recipient.",
            )
        # One-to-one sends address the participant, so echo the conversation
        # the caller replied in.
        response = SendResponse(**result)
        response.chat_id = response.chat_id or chat_id
        return response
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except MessagesDBBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except MessagesAutomationBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Send Attachment",
    description="Send a file attachment via Apple Messages to a recipient. Optionally include a text message.",
    annotations=ToolAnnotations(destructive_hint=True, idempotent_hint=False, open_world_hint=True),
    structured_output=True,
)
def messages_send_attachment(
    recipient: Annotated[str, Field(description=_RECIPIENT)],
    file_path: Annotated[str, Field(description="Absolute path of the local file to send.")],
    text: Annotated[str | None, Field(description="Optional message text sent after the file.")] = None,
    service_name: Annotated[str | None, Field(description=_SERVICE_NAME)] = None,
) -> SendResponse | ErrorResponse:
    try:
        ensure_action_allowed("messages_send_attachment")
        result = _automation_bridge().send_attachment(recipient=recipient, file_path=file_path, text=text, service_name=service_name)
        return SendResponse(**result)
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except MessagesAutomationBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


def _ensure_group_service_matches(chat_id: str, service_name: str | None) -> None:
    """Group sends go to the existing chat, which is bound to one service; reject a different service_name."""
    requested = normalize_service_name(service_name)
    if requested is None:
        return
    group_service = _db_bridge().latest_service_for_chat(chat_id)
    if group_service is not None and group_service.lower() == requested.lower():
        return
    current = f"uses {group_service}" if group_service else "has no known service"
    raise MessagesAutomationBridgeError(
        "INVALID_INPUT",
        f"service_name='{requested}' cannot be used for group chat {chat_id}: the group {current}, "
        "and Messages always sends a group reply over the group's existing service.",
        "Omit service_name to reply in the group as-is, or message participants individually "
        "with messages_send_message and service_name.",
    )


def _thread_service_preference(latest_service: str | None) -> list[str] | None:
    """Service order for a 1:1 reply, from the service of the thread's latest message."""
    latest = (latest_service or "").strip().lower()
    if latest == "rcs":
        return ["RCS", "SMS"]  # RCS threads can fall back to SMS, as the iPhone does
    if latest == "sms":
        return ["SMS"]
    return None  # iMessage or unknown: keep the default


def _serialize_prompt_messages(messages: list[PromptMessage]) -> list[dict[str, object]]:
    return [
        {
            "role": getattr(message, "role", "user"),
            "content": message.content.model_dump(mode="json") if hasattr(message.content, "model_dump") else message.content,
        }
        for message in messages
    ]


@mcp.tool(
    title="Messages List Prompts",
    description="Fallback prompt discovery tool for tool-only MCP clients.",
    annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
    structured_output=True,
)
async def messages_list_prompts() -> dict[str, object]:
    prompts = await mcp.list_prompts()
    return {
        "ok": True,
        "prompts": [{"name": prompt.name, "title": prompt.title, "description": prompt.description} for prompt in prompts],
        "count": len(prompts),
    }


@mcp.tool(
    name="messages_get_prompt",
    title="Messages Get Prompt",
    description="Fallback prompt rendering tool for tool-only MCP clients.",
    annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
    structured_output=True,
)
async def messages_get_prompt_prompt(
    name: Annotated[str, Field(description="Prompt name from messages_list_prompts.")],
    arguments_json: Annotated[str | None, Field(description="Prompt arguments as a JSON object string; omit when the prompt takes none.")] = None,
) -> dict[str, object]:
    arguments = json.loads(arguments_json) if arguments_json else None
    prompt = await mcp.get_prompt(name, arguments)
    if isinstance(prompt, InputRequiredResult):
        return {"ok": False, "name": name, "error": {"error_code": "PROMPT_INPUT_REQUIRED", "message": f"Prompt '{name}' needs client input before it can render."}}
    return {"ok": True, "name": name, "messages": _serialize_prompt_messages(prompt.messages), "message_count": len(prompt.messages)}


TOOL_DISCOVERY = install_search_first_discovery(
    mcp,
    server_name="Apple Messages MCP",
    domain="messages",
)


def main() -> None:
    transport = os.environ.get("APPLE_MESSAGES_MCP_TRANSPORT", "stdio")
    if transport == "streamable-http":
        mcp.run(
            transport="streamable-http",
            host=require_loopback_host(os.environ.get("APPLE_MESSAGES_MCP_HOST", "127.0.0.1")),
            port=int(os.environ.get("APPLE_MESSAGES_MCP_PORT", "8737")),
            json_response=True,
            stateless_http=False,
        )
        return
    mcp.run(transport="stdio")
