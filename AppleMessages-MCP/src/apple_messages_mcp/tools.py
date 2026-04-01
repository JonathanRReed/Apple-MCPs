from __future__ import annotations

import json

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import Annotations, ToolAnnotations

from apple_messages_mcp.config import load_settings
from apple_messages_mcp.messages_automation_bridge import MessagesAutomationBridge, MessagesAutomationBridgeError
from apple_messages_mcp.messages_db_bridge import MessagesDBBridge, MessagesDBBridgeError
from apple_messages_mcp.models import AttachmentListResponse, ConversationListResponse, ConversationResponse, ErrorResponse, HealthResponse, MessageResponse, MessageSearchResponse, MessagesCapabilities, SendResponse, ToolError
from apple_messages_mcp.permissions import SafetyError, ensure_action_allowed

SERVER_INSTRUCTIONS = (
    "Use this server for Apple Messages on macOS. "
    "Search here when the user wants to inspect message history, summarize conversations, search what someone said, or send and reply through Messages. "
    "History features require Full Disk Access, while send features require Messages automation permission."
)

mcp = FastMCP("Apple Messages MCP", instructions=SERVER_INSTRUCTIONS, json_response=True)


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
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
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
        capabilities=caps,
        history_access=history_access,
        automation_access=automation_access,
        history_access_error=history_error.message if history_error is not None else None,
        history_access_suggestion=history_error.suggestion if history_error is not None else None,
        automation_access_error=automation_error.message if automation_error is not None else None,
        automation_access_suggestion=automation_error.suggestion if automation_error is not None else None,
        transport=settings.transport,
    )


@mcp.tool(
    title="Messages Permission Guide",
    description="Explain how to grant Apple Messages permissions on macOS.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
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
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=False),
    structured_output=True,
)
async def messages_recheck_permissions(ctx: Context) -> HealthResponse:
    await ctx.report_progress(25, 100, "Rechecking Messages access")
    response = messages_health()
    await ctx.session.send_resource_list_changed()
    await ctx.report_progress(100, 100, "Done")
    return response


@mcp.tool(
    title="List Conversations",
    description="List recent Apple Messages conversations.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def messages_list_conversations(limit: int | str = 25, offset: int | str = 0, unread_only: bool = False) -> ConversationListResponse | ErrorResponse:
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
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def messages_get_conversation(chat_id: str, limit: int | str = 50, offset: int | str = 0) -> ConversationResponse | ErrorResponse:
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
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def messages_search_messages(
    query: str,
    chat_id: str | None = None,
    sender: str | None = None,
    start_iso: str | None = None,
    end_iso: str | None = None,
    limit: int | str = 50,
    offset: int | str = 0,
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
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def messages_get_message(message_id: str) -> MessageResponse | ErrorResponse:
    try:
        ensure_action_allowed("messages_get_message")
        message = _db_bridge().get_message(message_id)
        return MessageResponse(message=message)
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except MessagesDBBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="List Attachments",
    description="List Apple Messages attachments by chat or message.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def messages_list_attachments(chat_id: str | None = None, message_id: str | None = None, limit: int | str = 50, offset: int | str = 0) -> AttachmentListResponse | ErrorResponse:
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
    description="Send a new iMessage through Messages.app.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=True),
    structured_output=True,
)
def messages_send_message(recipient: str, text: str, service_name: str | None = None) -> SendResponse | ErrorResponse:
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
    description="Reply to an Apple Messages conversation using its chat_id. Supports both one-to-one and group chats.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=True),
    structured_output=True,
)
def messages_reply_in_conversation(chat_id: str, text: str) -> SendResponse | ErrorResponse:
    try:
        ensure_action_allowed("messages_reply_in_conversation")
        participants = _db_bridge().participant_addresses_for_chat(chat_id)
        if len(participants) == 1:
            result = _automation_bridge().send_message(recipient=participants[0], text=text)
        elif len(participants) > 1:
            result = _automation_bridge().send_to_group(chat_id=chat_id, text=text)
        else:
            return _error_response(
                "EMPTY_CONVERSATION",
                "Could not determine participants for this conversation.",
                "Use messages_send_message with an explicit recipient.",
            )
        return SendResponse(**result)
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except MessagesDBBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except MessagesAutomationBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Send Attachment",
    description="Send a file attachment via Apple Messages to a recipient. Optionally include a text message.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=True),
    structured_output=True,
)
def messages_send_attachment(recipient: str, file_path: str, text: str | None = None) -> SendResponse | ErrorResponse:
    try:
        ensure_action_allowed("messages_send_attachment")
        result = _automation_bridge().send_attachment(recipient=recipient, file_path=file_path, text=text)
        return SendResponse(**result)
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except MessagesAutomationBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


def _serialize_prompt_messages(messages: list[object]) -> list[dict[str, object]]:
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
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
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
    title="Messages Get Prompt",
    description="Fallback prompt rendering tool for tool-only MCP clients.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
async def messages_get_prompt_prompt(name: str, arguments_json: str | None = None) -> dict[str, object]:
    arguments = json.loads(arguments_json) if arguments_json else None
    prompt = await mcp.get_prompt(name, arguments)
    return {"ok": True, "name": name, "messages": _serialize_prompt_messages(prompt.messages), "message_count": len(prompt.messages)}


@mcp._mcp_server.subscribe_resource()
async def _messages_subscribe_resource(uri) -> None:
    del uri


@mcp._mcp_server.unsubscribe_resource()
async def _messages_unsubscribe_resource(uri) -> None:
    del uri


def main() -> None:
    mcp.run(transport="stdio")
