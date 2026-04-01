from __future__ import annotations

import json

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import Annotations, ToolAnnotations

from apple_notes_mcp.config import load_settings
from apple_notes_mcp.models import (
    AccountListResponse,
    AttachmentListResponse,
    DeleteFolderResponse,
    ErrorResponse,
    FolderListResponse,
    FolderMutationResponse,
    HealthResponse,
    MoveNoteResponse,
    NoteListResponse,
    NoteResponse,
    NotesCapabilities,
    ToolError,
    DeleteNoteResponse,
)
from apple_notes_mcp.notes_bridge import AppleNotesBridge, NotesBridgeError, build_bridge
from apple_notes_mcp.permissions import SafetyError, ensure_action_allowed

SERVER_INSTRUCTIONS = (
    "Use this server for Apple Notes on macOS. "
    "Search here when the user wants to inspect notes, find references, create notes, update notes, move notes, or organize folders. "
    "Prefer list and get tools before mutations when ids are unknown."
)

mcp = FastMCP("Apple Notes MCP", instructions=SERVER_INSTRUCTIONS, json_response=True)


def _bridge() -> AppleNotesBridge:
    return build_bridge()


def _error_response(error_code: str, message: str, suggestion: str | None = None) -> ErrorResponse:
    return ErrorResponse(error=ToolError(error_code=error_code, message=message, suggestion=suggestion))


def _capabilities() -> NotesCapabilities:
    return NotesCapabilities()


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


def _folder_account_name(folder_id: str | None) -> str | None:
    if folder_id is None:
        return None
    for folder in _bridge().list_folders():
        if folder.folder_id == folder_id:
            return folder.account_name
    return None


def _folder_info(folder_id: str | None):
    if folder_id is None:
        return None
    for folder in _bridge().list_folders():
        if folder.folder_id == folder_id:
            return folder
    return None


@mcp.resource(
    "notes://folders",
    name="notes_folders_snapshot",
    title="Note Folders",
    description="Current Apple Notes folders.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.9),
)
def notes_folders_resource() -> str:
    folders = _bridge().list_folders()
    return _resource_json({"folders": [item.model_dump() for item in folders], "count": len(folders)})


@mcp.resource(
    "notes://recent",
    name="notes_recent_snapshot",
    title="Recent Notes",
    description="A compact snapshot of recently modified Apple Notes notes.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.8),
)
def notes_recent_resource() -> str:
    notes = sorted(_bridge().list_notes(), key=lambda item: item.modified_epoch or 0, reverse=True)[:25]
    return _resource_json({"notes": [item.model_dump() for item in notes], "count": len(notes)})


@mcp.resource(
    "notes://note/{note_id}",
    name="notes_note_detail",
    title="Note Detail",
    description="A single Apple Notes note.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.7),
)
def notes_note_resource(note_id: str) -> str:
    note = _bridge().get_note(note_id)
    return _resource_json(note.model_dump())


@mcp.prompt(name="notes_find_reference", title="Find Referenced Note")
def notes_find_reference_prompt() -> str:
    return (
        "Find the note that matches the user's reference, then inspect it and surface the relevant content. "
        "Use note search first, then open the most likely note."
    )


@mcp.prompt(name="notes_organize_topic", title="Organize Notes by Topic")
def notes_organize_topic_prompt() -> str:
    return (
        "Review the user's notes, group related notes by topic or folder, and suggest an organization plan. "
        "Use list and search tools before proposing moves or folder changes."
    )


@mcp.prompt(name="notes_create_from_conversation", title="Create Note from Conversation")
def notes_create_from_conversation_prompt() -> str:
    return (
        "Turn the current conversation into a useful Apple Notes note. "
        "Summarize the important details, choose a good folder, and create the note."
    )


@mcp.prompt(name="notes_cleanup", title="Clean Up Notes")
def notes_cleanup_prompt() -> str:
    return (
        "Audit the user's notes folders, identify clutter, and suggest concrete cleanup actions. "
        "Prefer renaming, moving, and merging folders over deleting unless the user asks for deletion."
    )


@mcp.tool(
    title="Notes Health",
    description="Report the active Apple Notes MCP configuration.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def notes_health() -> HealthResponse:
    settings = load_settings()
    return HealthResponse(
        server_name=settings.server_name,
        version=settings.version,
        safety_mode=settings.safety_mode,
        capabilities=_capabilities(),
    )


@mcp.tool(
    title="Notes Permission Guide",
    description="Explain how to grant Apple Notes automation permission on macOS.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def notes_permission_guide() -> dict[str, object]:
    return {
        "ok": True,
        "domain": "notes",
        "can_prompt_in_app": True,
        "requires_manual_system_settings": False,
        "steps": [
            "Call a Notes tool from this MCP server.",
            "Approve the macOS Automation prompt for Notes if it appears.",
            "If access was denied before, re-enable it in System Settings > Privacy & Security > Automation.",
        ],
    }


@mcp.tool(
    title="Notes Recheck Permissions",
    description="Recheck Notes access after the user changes macOS permissions, and notify the client that Notes resources changed.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=False),
    structured_output=True,
)
async def notes_recheck_permissions(ctx: Context) -> HealthResponse:
    await ctx.report_progress(25, 100, "Rechecking Notes access")
    response = notes_health()
    await ctx.session.send_resource_list_changed()
    await ctx.report_progress(100, 100, "Done")
    return response


@mcp.tool(
    title="List Accounts",
    description="List Apple Notes accounts.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def notes_list_accounts() -> AccountListResponse | ErrorResponse:
    try:
        ensure_action_allowed("notes_list_accounts")
        accounts = _bridge().list_accounts()
        return AccountListResponse(accounts=accounts, count=len(accounts))
    except (SafetyError, NotesBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="List Folders",
    description="List Apple Notes folders.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def notes_list_folders(account_name: str | None = None, limit: int | str = 100, offset: int | str = 0) -> FolderListResponse | ErrorResponse:
    try:
        limit_value = _coerce_int_arg("limit", limit, minimum=1)
        offset_value = _coerce_int_arg("offset", offset, minimum=0)
        ensure_action_allowed("notes_list_folders", account_name)
        folders = _bridge().list_folders(account_name=account_name)
        page = folders[offset_value : offset_value + limit_value]
        return FolderListResponse(folders=page, count=len(page))
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except NotesBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except ValueError as exc:
        return _error_response("INVALID_INPUT", str(exc), "Provide a positive limit and a non-negative offset.")


@mcp.tool(
    title="List Notes",
    description="List notes, optionally scoped to a folder or account.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def notes_list_notes(account_name: str | None = None, folder_id: str | None = None, limit: int | str = 100, offset: int | str = 0) -> NoteListResponse | ErrorResponse:
    try:
        limit_value = _coerce_int_arg("limit", limit, minimum=1)
        offset_value = _coerce_int_arg("offset", offset, minimum=0)
        folder = _folder_info(folder_id)
        ensure_action_allowed("notes_list_notes", account_name or (folder.account_name if folder is not None else None), folder.name if folder is not None else None)
        notes = _bridge().list_notes(account_name=account_name, folder_id=folder_id)
        page = notes[offset_value : offset_value + limit_value]
        return NoteListResponse(notes=page, count=len(page))
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except NotesBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except ValueError as exc:
        return _error_response("INVALID_INPUT", str(exc), "Provide a positive limit and a non-negative offset.")


@mcp.tool(
    title="Get Note",
    description="Fetch full details for an Apple Notes note by note_id.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def notes_get_note(note_id: str) -> NoteResponse | ErrorResponse:
    try:
        note = _bridge().get_note(note_id)
        ensure_action_allowed("notes_get_note", note.account_name, note.folder_name)
        return NoteResponse(note=note)
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except NotesBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Search Notes",
    description="Search notes by text, folder, or account.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def notes_search_notes(query: str, account_name: str | None = None, folder_id: str | None = None, limit: int | str = 25, offset: int | str = 0) -> NoteListResponse | ErrorResponse:
    try:
        limit_value = _coerce_int_arg("limit", limit, minimum=1)
        offset_value = _coerce_int_arg("offset", offset, minimum=0)
        folder = _folder_info(folder_id)
        ensure_action_allowed("notes_search_notes", account_name or (folder.account_name if folder is not None else None), folder.name if folder is not None else None)
        notes = _bridge().search_notes(query=query, account_name=account_name, folder_id=folder_id, limit=100)
        page = notes[offset_value : offset_value + limit_value]
        return NoteListResponse(notes=page, count=len(page))
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except NotesBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except ValueError as exc:
        return _error_response("INVALID_INPUT", str(exc), "Provide a positive limit and a non-negative offset.")


@mcp.tool(
    title="Create Note",
    description="Create a new note in a folder.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def notes_create_note(title: str, folder_id: str, body_html: str | None = None, tags: list[str] | None = None) -> NoteResponse | ErrorResponse:
    try:
        if not title.strip():
            raise ValueError("title must not be empty")
        folder = _folder_info(folder_id)
        account_name = folder.account_name if folder is not None else None
        ensure_action_allowed("notes_create_note", account_name, folder.name if folder is not None else None)
        note = _bridge().create_note(title=title.strip(), folder_id=folder_id, body_html=body_html, tags=tags)
        return NoteResponse(note=note)
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except NotesBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except ValueError as exc:
        return _error_response("INVALID_INPUT", str(exc), "Provide a non-empty title.")


@mcp.tool(
    title="Update Note",
    description="Update an existing note.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def notes_update_note(note_id: str, title: str | None = None, body_html: str | None = None, folder_id: str | None = None, tags: list[str] | None = None) -> NoteResponse | ErrorResponse:
    try:
        current = _bridge().get_note(note_id)
        target_folder = _folder_info(folder_id) if folder_id is not None else None
        target_account = target_folder.account_name if target_folder is not None else current.account_name
        target_folder_name = target_folder.name if target_folder is not None else current.folder_name
        ensure_action_allowed("notes_update_note", target_account, target_folder_name)
        note = _bridge().update_note(note_id, title=title, body_html=body_html, folder_id=folder_id, tags=tags)
        return NoteResponse(note=note)
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except NotesBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Append to Note",
    description="Append text to an existing note without replacing its current content. Provide body_text for plain text or body_html for rich content.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def notes_append_to_note(note_id: str, body_text: str | None = None, body_html: str | None = None) -> NoteResponse | ErrorResponse:
    try:
        current = _bridge().get_note(note_id)
        ensure_action_allowed("notes_append_to_note", current.account_name, current.folder_name)
        if body_html is None and body_text is not None:
            from html import escape as html_escape

            lines = body_text.splitlines() or [body_text]
            body_html = "".join(f"<div>{html_escape(line)}</div>" if line.strip() else "<div><br></div>" for line in lines)
        if not body_html:
            return _error_response("INVALID_INPUT", "Provide body_text or body_html.", "Supply at least one of body_text or body_html.")
        note = _bridge().append_to_note(note_id, body_html)
        return NoteResponse(note=note)
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except NotesBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Delete Note",
    description="Delete a note by note_id.",
    annotations=ToolAnnotations(destructiveHint=True, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def notes_delete_note(note_id: str) -> DeleteNoteResponse | ErrorResponse:
    try:
        current = _bridge().get_note(note_id)
        ensure_action_allowed("notes_delete_note", current.account_name, current.folder_name)
        deleted = _bridge().delete_note(note_id)
        return DeleteNoteResponse(deleted=deleted, note_id=note_id)
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except NotesBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Move Note",
    description="Move a note to a different folder.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def notes_move_note(note_id: str, folder_id: str) -> MoveNoteResponse | ErrorResponse:
    try:
        target_folder = _folder_info(folder_id)
        target_account = target_folder.account_name if target_folder is not None else None
        ensure_action_allowed("notes_move_note", target_account, target_folder.name if target_folder is not None else None)
        note = _bridge().move_note(note_id, folder_id)
        return MoveNoteResponse(note=note)
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except NotesBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Create Folder",
    description="Create a new folder in an Apple Notes account or nested folder.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def notes_create_folder(folder_name: str, account_name: str, parent_folder_id: str | None = None) -> FolderMutationResponse | ErrorResponse:
    try:
        if not folder_name.strip():
            raise ValueError("folder_name must not be empty")
        ensure_action_allowed("notes_create_folder", account_name, None)
        folder = _bridge().create_folder(folder_name=folder_name.strip(), account_name=account_name, parent_folder_id=parent_folder_id)
        return FolderMutationResponse(folder=folder)
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except NotesBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except ValueError as exc:
        return _error_response("INVALID_INPUT", str(exc), "Provide a non-empty folder name.")


@mcp.tool(
    title="Rename Folder",
    description="Rename an existing folder.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def notes_rename_folder(folder_id: str, folder_name: str) -> FolderMutationResponse | ErrorResponse:
    try:
        folder = _bridge().list_folders()
        target = next((item for item in folder if item.folder_id == folder_id), None)
        if target is not None:
            ensure_action_allowed("notes_rename_folder", target.account_name, target.name)
        renamed = _bridge().rename_folder(folder_id, folder_name)
        return FolderMutationResponse(folder=renamed)
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except NotesBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Delete Folder",
    description="Delete an Apple Notes folder.",
    annotations=ToolAnnotations(destructiveHint=True, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def notes_delete_folder(folder_id: str) -> DeleteFolderResponse | ErrorResponse:
    try:
        folder = next((item for item in _bridge().list_folders() if item.folder_id == folder_id), None)
        if folder is not None:
            ensure_action_allowed("notes_delete_folder", folder.account_name, folder.name)
        deleted = _bridge().delete_folder(folder_id)
        return DeleteFolderResponse(deleted=deleted, folder_id=folder_id)
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except NotesBridgeError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="List Attachments",
    description="List attachments for a note.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def notes_list_attachments(note_id: str) -> AttachmentListResponse | ErrorResponse:
    try:
        note = _bridge().get_note(note_id)
        ensure_action_allowed("notes_list_attachments", note.account_name, note.folder_name)
        return AttachmentListResponse(attachments=note.attachments, count=len(note.attachments))
    except SafetyError as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)
    except NotesBridgeError as exc:
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
    title="Notes List Prompts",
    description="Fallback prompt discovery tool for tool-only MCP clients.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
async def notes_list_prompts() -> dict[str, object]:
    prompts = await mcp.list_prompts()
    return {
        "ok": True,
        "prompts": [{"name": prompt.name, "title": prompt.title, "description": prompt.description} for prompt in prompts],
        "count": len(prompts),
    }


@mcp.tool(
    title="Notes Get Prompt",
    description="Fallback prompt rendering tool for tool-only MCP clients.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
async def notes_get_prompt_prompt(name: str, arguments_json: str | None = None) -> dict[str, object]:
    arguments = json.loads(arguments_json) if arguments_json else None
    prompt = await mcp.get_prompt(name, arguments)
    return {"ok": True, "name": name, "messages": _serialize_prompt_messages(prompt.messages), "message_count": len(prompt.messages)}


@mcp._mcp_server.subscribe_resource()
async def _notes_subscribe_resource(uri) -> None:
    del uri


@mcp._mcp_server.unsubscribe_resource()
async def _notes_unsubscribe_resource(uri) -> None:
    del uri


def main() -> None:
    mcp.run(transport="stdio")
