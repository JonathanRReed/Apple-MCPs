from __future__ import annotations

import json

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import Annotations, ToolAnnotations

from apple_contacts_mcp.config import load_settings
from apple_contacts_mcp.contacts_bridge import AppleContactsBridge, ContactsBridgeError, build_bridge
from apple_contacts_mcp.models import ContactListResponse, ContactMethod, ContactResponse, CreateContactResponse, DeleteContactResponse, ErrorResponse, HealthResponse, ResolvedRecipientResponse, ToolError
from apple_contacts_mcp.permissions import SafetyError, ensure_action_allowed

SERVER_INSTRUCTIONS = (
    "Use this server for Apple Contacts on macOS. "
    "Search here when the user wants to inspect contacts, find a phone number or email address, "
    "or resolve a contact into a message-ready recipient before using Apple Messages."
)

mcp = FastMCP("Apple Contacts", instructions=SERVER_INSTRUCTIONS, json_response=True)


def _bridge() -> AppleContactsBridge:
    return build_bridge()


def _error_response(error_code: str, message: str, suggestion: str | None = None) -> ErrorResponse:
    return ErrorResponse(error=ToolError(error_code=error_code, message=message, suggestion=suggestion))


def _resource_json(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, default=str)


@mcp.resource(
    "contacts://directory",
    name="contacts_directory",
    title="Contacts Directory",
    description="A compact Apple Contacts directory snapshot.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.8),
)
def contacts_directory_resource() -> str:
    contacts = _bridge().list_contacts()[:100]
    return _resource_json({"contacts": [item.model_dump() for item in contacts], "count": len(contacts)})


@mcp.resource(
    "contacts://contact/{contact_id}",
    name="contacts_detail",
    title="Contact Detail",
    description="A single Apple Contacts record.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.7),
)
def contacts_contact_resource(contact_id: str) -> str:
    contact = _bridge().get_contact(contact_id)
    return _resource_json(contact.model_dump())


@mcp.prompt(name="contacts_prepare_message_recipient", title="Prepare Message Recipient")
def contacts_prepare_message_recipient_prompt() -> str:
    return (
        "Use Apple Contacts to find the right recipient, verify the phone number or email address, "
        "and return the best message-ready contact method before using Apple Messages."
    )


@mcp.tool(
    title="Contacts Health",
    description="Report the active Apple Contacts MCP configuration.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def contacts_health() -> HealthResponse:
    settings = load_settings()
    accessible, error = _bridge().permission_diagnostic()
    capabilities = [
        "list_contacts",
        "search_contacts",
        "get_contact",
        "resolve_message_recipient",
        "resources",
        "prompts",
    ]
    if settings.safety_mode in {"safe_manage", "full_access"}:
        capabilities.extend(["create_contact", "update_contact"])
    if settings.safety_mode == "full_access":
        capabilities.append("delete_contact")
    return HealthResponse(
        server_name=settings.server_name,
        version=settings.version,
        safety_mode=settings.safety_mode,
        capabilities=capabilities,
        contacts_accessible=accessible,
        permission_error=error.message if error is not None else None,
        permission_suggestion=error.suggestion if error is not None else None,
    )


@mcp.tool(
    title="Contacts Permission Guide",
    description="Explain how to grant Apple Contacts permission on macOS.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def contacts_permission_guide() -> dict[str, object]:
    return {
        "ok": True,
        "domain": "contacts",
        "can_prompt_in_app": True,
        "requires_manual_system_settings": False,
        "steps": [
            "Call a Contacts tool from this MCP server.",
            "Approve the macOS Contacts access prompt when it appears.",
            "If access was denied before, re-enable it in System Settings > Privacy & Security > Contacts.",
        ],
    }


@mcp.tool(
    title="Contacts Recheck Permissions",
    description="Recheck Contacts access after the user changes macOS permissions, and notify the client that Contacts resources changed.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=False),
    structured_output=True,
)
async def contacts_recheck_permissions(ctx: Context) -> HealthResponse:
    await ctx.report_progress(25, 100, "Rechecking Contacts access")
    response = contacts_health()
    await ctx.session.send_resource_list_changed()
    await ctx.report_progress(100, 100, "Done")
    return response


@mcp.tool(
    title="List Contacts",
    description="List Apple Contacts entries.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def contacts_list_contacts(limit: int = 100, offset: int = 0) -> ContactListResponse | ErrorResponse:
    try:
        if limit < 1:
            raise ValueError("limit must be greater than zero")
        if offset < 0:
            raise ValueError("offset must not be negative")
        ensure_action_allowed("contacts_list_contacts")
        contacts = _bridge().list_contacts()
        page = contacts[offset : offset + limit]
        return ContactListResponse(contacts=page, count=len(page))
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except ContactsBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except ValueError as exc:
        return _error_response("INVALID_INPUT", str(exc), "Provide a positive limit and a non-negative offset.")


@mcp.tool(
    title="Search Contacts",
    description="Search Apple Contacts by name, phone number, or email address.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def contacts_search_contacts(query: str, limit: int = 25) -> ContactListResponse | ErrorResponse:
    try:
        if limit < 1:
            raise ValueError("limit must be greater than zero")
        ensure_action_allowed("contacts_search_contacts")
        contacts = _bridge().search_contacts(query=query, limit=limit)
        return ContactListResponse(contacts=contacts, count=len(contacts))
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except ContactsBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except ValueError as exc:
        return _error_response("INVALID_INPUT", str(exc), "Provide a positive limit.")


@mcp.tool(
    title="Get Contact",
    description="Fetch full details for an Apple Contacts record by contact_id.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def contacts_get_contact(contact_id: str) -> ContactResponse | ErrorResponse:
    try:
        ensure_action_allowed("contacts_get_contact")
        return ContactResponse(contact=_bridge().get_contact(contact_id))
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except ContactsBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Resolve Message Recipient",
    description="Resolve a contact into a message-ready phone number or email address.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def contacts_resolve_message_recipient(query: str, channel: str = "phone") -> ResolvedRecipientResponse | ErrorResponse:
    try:
        ensure_action_allowed("contacts_resolve_message_recipient")
        return _bridge().resolve_message_recipient(query=query, channel=channel)
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except ContactsBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Create Contact",
    description="Create a new contact in Apple Contacts with a first name (required) and optional last name, organization, and note.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def contacts_create_contact(
    first_name: str,
    last_name: str = "",
    organization: str = "",
    phones: list[ContactMethod] | None = None,
    emails: list[ContactMethod] | None = None,
    note: str = "",
) -> CreateContactResponse | ErrorResponse:
    try:
        ensure_action_allowed("contacts_create_contact")
        return _bridge().create_contact(
            first_name=first_name,
            last_name=last_name,
            organization=organization,
            phones=phones,
            emails=emails,
            note=note,
        )
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except ContactsBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Update Contact",
    description="Update an existing contact's information. Only the fields you provide will be changed.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def contacts_update_contact(
    contact_id: str,
    first_name: str = "",
    last_name: str = "",
    organization: str = "",
    phones: list[ContactMethod] | None = None,
    emails: list[ContactMethod] | None = None,
    note: str = "",
) -> ContactResponse | ErrorResponse:
    try:
        ensure_action_allowed("contacts_update_contact")
        contact = _bridge().update_contact(
            contact_id,
            first_name=first_name,
            last_name=last_name,
            organization=organization,
            phones=phones,
            emails=emails,
            note=note,
        )
        return ContactResponse(contact=contact)
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except ContactsBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Delete Contact",
    description="Permanently delete a contact by contact_id. Requires full_access safety mode.",
    annotations=ToolAnnotations(destructiveHint=True, idempotentHint=True, openWorldHint=False),
    structured_output=True,
)
def contacts_delete_contact(contact_id: str) -> DeleteContactResponse | ErrorResponse:
    try:
        ensure_action_allowed("contacts_delete_contact")
        return _bridge().delete_contact(contact_id)
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except ContactsBridgeError as exc:
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
    title="Contacts List Prompts",
    description="Fallback prompt discovery tool for tool-only MCP clients.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
async def contacts_list_prompts() -> dict[str, object]:
    prompts = await mcp.list_prompts()
    return {
        "ok": True,
        "prompts": [{"name": prompt.name, "title": prompt.title, "description": prompt.description} for prompt in prompts],
        "count": len(prompts),
    }


@mcp.tool(
    title="Contacts Get Prompt",
    description="Fallback prompt rendering tool for tool-only MCP clients.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
async def contacts_get_prompt_prompt(name: str, arguments_json: str | None = None) -> dict[str, object]:
    arguments = json.loads(arguments_json) if arguments_json else None
    prompt = await mcp.get_prompt(name, arguments)
    return {"ok": True, "name": name, "messages": _serialize_prompt_messages(prompt.messages), "message_count": len(prompt.messages)}


@mcp._mcp_server.subscribe_resource()
async def _contacts_subscribe_resource(uri) -> None:
    del uri


@mcp._mcp_server.unsubscribe_resource()
async def _contacts_unsubscribe_resource(uri) -> None:
    del uri


def main() -> None:
    mcp.run(transport="stdio")
