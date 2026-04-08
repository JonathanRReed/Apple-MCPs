from __future__ import annotations

import json

from apple_mcp_common.discovery import install_search_first_discovery
from mcp.server.fastmcp import Context, FastMCP
from mcp.types import Annotations, ToolAnnotations

from apple_files_mcp.config import load_settings
from apple_files_mcp.files_bridge import FilesBridgeError, build_bridge
from apple_files_mcp.models import ErrorResponse, FileActionResponse, FileListResponse, FileMutationResponse, FileResponse, FileTagsResponse, FileTextResponse, HealthResponse, ICloudStatusResponse, RecentLocationsResponse, RootsResponse, ToolError
from apple_files_mcp.permissions import SafetyError, ensure_action_allowed

SERVER_INSTRUCTIONS = (
    "Use this server for file and folder access on macOS. "
    "Search here when the user wants to inspect Downloads, Desktop, Documents, iCloud Drive, or other allowed folders, "
    "read a text file, prepare an attachment, create a folder, move a file, open or reveal a path, manage Finder tags, or delete a path."
)

mcp = FastMCP("Apple Files MCP", instructions=SERVER_INSTRUCTIONS, json_response=True)


def _bridge():
    return build_bridge()


def _error_response(error_code: str, message: str, suggestion: str | None = None) -> ErrorResponse:
    return ErrorResponse(error=ToolError(error_code=error_code, message=message, suggestion=suggestion))


def _resource_json(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, default=str)


@mcp.resource(
    "files://allowed-roots",
    name="files_allowed_roots",
    title="Allowed File Roots",
    description="The file system roots this MCP server is allowed to access.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.9),
)
def files_allowed_roots_resource() -> str:
    roots = _bridge().list_allowed_roots()
    return _resource_json({"roots": roots, "count": len(roots)})


@mcp.resource(
    "files://recent",
    name="files_recent",
    title="Recent Files",
    description="A compact snapshot of recently modified files inside the allowed roots.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.8),
)
def files_recent_resource() -> str:
    entries = _bridge().recent_files(limit=25)
    return _resource_json({"files": [item.model_dump() for item in entries], "count": len(entries)})


@mcp.resource(
    "files://recent-locations",
    name="files_recent_locations",
    title="Recent File Locations",
    description="Recently active parent folders across the allowed roots, including iCloud-aware metadata.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.78),
)
def files_recent_locations_resource() -> str:
    entries = _bridge().list_recent_locations(limit=15)
    return _resource_json({"locations": [item.model_dump() for item in entries], "count": len(entries)})


@mcp.resource(
    "files://icloud-status",
    name="files_icloud_status",
    title="iCloud Drive Status",
    description="Availability and allowed-root status for local iCloud Drive access.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.76),
)
def files_icloud_status_resource() -> str:
    return _resource_json(_bridge().icloud_status())


@mcp.prompt(name="files_prepare_attachment", title="Prepare Attachment")
def files_prepare_attachment_prompt() -> str:
    return (
        "Use Apple Files to locate the right document, confirm its path and modification time, "
        "and return the exact file path before attaching it to Mail, Messages, Notes, or Shortcuts."
    )


@mcp.prompt(name="files_organize_workspace", title="Organize Workspace")
def files_organize_workspace_prompt() -> str:
    return (
        "Inspect the allowed roots, identify the right folder for the requested work, "
        "and suggest file moves or folder creation only when the organization goal is clear."
    )


@mcp.tool(
    title="Files Health",
    description="Report the active Apple Files MCP configuration.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def files_health() -> HealthResponse:
    settings = load_settings()
    capabilities = [
        "list_allowed_roots",
        "list_directory",
        "search_files",
        "get_file_info",
        "read_text_file",
        "recent_files",
        "get_tags",
        "list_recent_locations",
        "get_icloud_status",
        "resources",
        "prompts",
    ]
    if settings.safety_mode in {"safe_manage", "full_access"}:
        capabilities.extend(["create_folder", "move_path", "open_path", "reveal_in_finder", "set_tags", "add_tags", "remove_tags"])
    if settings.safety_mode == "full_access":
        capabilities.append("delete_path")
    return HealthResponse(
        server_name=settings.server_name,
        version=settings.version,
        safety_mode=settings.safety_mode,
        allowed_roots=[str(path) for path in settings.allowed_roots],
        transport=settings.transport,
        capabilities=capabilities,
        supports=["stdio", "streamable-http"],
    )


@mcp.tool(
    title="Files Permission Guide",
    description="Explain how Apple Files MCP access is scoped on this machine.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def files_permission_guide() -> dict[str, object]:
    settings = load_settings()
    return {
        "ok": True,
        "domain": "files",
        "can_prompt_in_app": False,
        "requires_manual_system_settings": False,
        "steps": [
            "Use files_list_allowed_roots to inspect the current file access scope.",
            "If you need a broader file scope, restart the MCP with APPLE_FILES_MCP_ALLOWED_ROOTS set to a comma-separated list of root folders.",
            "Use APPLE_FILES_MCP_SAFETY_MODE=safe_manage or full_access only when mutation tools are actually needed.",
            "iCloud Drive is supported through the local Mobile Documents root when it exists on this Mac.",
        ],
        "notes": [
            f"Current safety mode: {settings.safety_mode}",
            f"Allowed roots: {', '.join(str(path) for path in settings.allowed_roots)}",
        ],
    }


@mcp.tool(
    title="List Allowed Roots",
    description="List the file system roots the server may access.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def files_list_allowed_roots() -> RootsResponse:
    roots = _bridge().list_allowed_roots()
    return RootsResponse(roots=roots, count=len(roots))


@mcp.tool(
    title="List Directory",
    description="List files and folders inside an allowed directory path.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def files_list_directory(path: str) -> FileListResponse | ErrorResponse:
    try:
        ensure_action_allowed("files_list_directory")
        entries = _bridge().list_directory(path)
        return FileListResponse(base_path=path, entries=entries, count=len(entries))
    except (SafetyError, FilesBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, getattr(exc, "suggestion", None))


@mcp.tool(
    title="Search Files",
    description="Search file and folder names inside the allowed roots.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def files_search_files(query: str, base_path: str | None = None, limit: int = 25) -> FileListResponse | ErrorResponse:
    try:
        ensure_action_allowed("files_search_files")
        entries = _bridge().search_files(query=query, base_path=base_path, limit=limit)
        return FileListResponse(base_path=base_path or "allowed-roots", entries=entries, count=len(entries))
    except (SafetyError, FilesBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, getattr(exc, "suggestion", None))


@mcp.tool(
    title="Get File Info",
    description="Get metadata for a file or folder inside the allowed roots.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def files_get_file_info(path: str) -> FileResponse | ErrorResponse:
    try:
        ensure_action_allowed("files_get_file_info")
        return FileResponse(entry=_bridge().file_info(path))
    except (SafetyError, FilesBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, getattr(exc, "suggestion", None))


@mcp.tool(
    title="Read Text File",
    description="Read a UTF-8 text file inside the allowed roots.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def files_read_text_file(path: str, max_bytes: int = 100_000) -> FileTextResponse | ErrorResponse:
    try:
        ensure_action_allowed("files_read_text_file")
        text, truncated = _bridge().read_text_file(path=path, max_bytes=max_bytes)
        return FileTextResponse(path=path, text=text, truncated=truncated)
    except (SafetyError, FilesBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, getattr(exc, "suggestion", None))


@mcp.tool(
    title="Recent Files",
    description="List recently modified files inside the allowed roots.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def files_recent_files(limit: int = 25) -> FileListResponse | ErrorResponse:
    try:
        ensure_action_allowed("files_recent_files")
        entries = _bridge().recent_files(limit=limit)
        return FileListResponse(base_path="allowed-roots", entries=entries, count=len(entries))
    except (SafetyError, FilesBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, getattr(exc, "suggestion", None))


@mcp.tool(
    title="Open Path",
    description="Open a file or folder in the default app. Requires safe_manage or full_access safety mode.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=True),
    structured_output=True,
)
def files_open_path(path: str) -> FileActionResponse | ErrorResponse:
    try:
        ensure_action_allowed("files_open_path")
        opened = _bridge().open_path(path)
        info = _bridge().file_info(opened)
        return FileActionResponse(path=opened, action="opened", opened=True, revealed=False, is_icloud=info.is_icloud)
    except (SafetyError, FilesBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, getattr(exc, "suggestion", None))


@mcp.tool(
    title="Reveal In Finder",
    description="Reveal a file or folder in Finder. Requires safe_manage or full_access safety mode.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=True),
    structured_output=True,
)
def files_reveal_in_finder(path: str) -> FileActionResponse | ErrorResponse:
    try:
        ensure_action_allowed("files_reveal_in_finder")
        revealed = _bridge().reveal_in_finder(path)
        info = _bridge().file_info(revealed)
        return FileActionResponse(path=revealed, action="revealed", opened=False, revealed=True, is_icloud=info.is_icloud)
    except (SafetyError, FilesBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, getattr(exc, "suggestion", None))


@mcp.tool(
    title="Get Tags",
    description="Read Finder tags for a file or folder inside the allowed roots.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def files_get_tags(path: str) -> FileTagsResponse | ErrorResponse:
    try:
        ensure_action_allowed("files_get_tags")
        resolved_path, tags, is_icloud = _bridge().get_tags(path)
        return FileTagsResponse(path=resolved_path, tags=tags, count=len(tags), is_icloud=is_icloud)
    except (SafetyError, FilesBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, getattr(exc, "suggestion", None))


@mcp.tool(
    title="Set Tags",
    description="Replace Finder tags for a file or folder. Requires safe_manage or full_access safety mode.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def files_set_tags(path: str, tags: list[str]) -> FileTagsResponse | ErrorResponse:
    try:
        ensure_action_allowed("files_set_tags")
        resolved_path, current_tags, is_icloud = _bridge().set_tags(path, tags)
        return FileTagsResponse(path=resolved_path, tags=current_tags, count=len(current_tags), is_icloud=is_icloud)
    except (SafetyError, FilesBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, getattr(exc, "suggestion", None))


@mcp.tool(
    title="Add Tags",
    description="Add Finder tags to a file or folder. Requires safe_manage or full_access safety mode.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def files_add_tags(path: str, tags: list[str]) -> FileTagsResponse | ErrorResponse:
    try:
        ensure_action_allowed("files_add_tags")
        resolved_path, current_tags, is_icloud = _bridge().add_tags(path, tags)
        return FileTagsResponse(path=resolved_path, tags=current_tags, count=len(current_tags), is_icloud=is_icloud)
    except (SafetyError, FilesBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, getattr(exc, "suggestion", None))


@mcp.tool(
    title="Remove Tags",
    description="Remove Finder tags from a file or folder. Requires safe_manage or full_access safety mode.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def files_remove_tags(path: str, tags: list[str]) -> FileTagsResponse | ErrorResponse:
    try:
        ensure_action_allowed("files_remove_tags")
        resolved_path, current_tags, is_icloud = _bridge().remove_tags(path, tags)
        return FileTagsResponse(path=resolved_path, tags=current_tags, count=len(current_tags), is_icloud=is_icloud)
    except (SafetyError, FilesBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, getattr(exc, "suggestion", None))


@mcp.tool(
    title="List Recent Locations",
    description="List recently active parent folders across the allowed roots, including iCloud-aware metadata.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def files_list_recent_locations(limit: int = 15) -> RecentLocationsResponse | ErrorResponse:
    try:
        ensure_action_allowed("files_list_recent_locations")
        entries = _bridge().list_recent_locations(limit=limit)
        return RecentLocationsResponse(locations=entries, count=len(entries))
    except (SafetyError, FilesBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, getattr(exc, "suggestion", None))


@mcp.tool(
    title="Get iCloud Status",
    description="Report whether local iCloud Drive is available and whether it is part of the current allowed roots.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def files_get_icloud_status() -> ICloudStatusResponse | ErrorResponse:
    try:
        ensure_action_allowed("files_get_icloud_status")
        return ICloudStatusResponse(**_bridge().icloud_status())
    except (SafetyError, FilesBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, getattr(exc, "suggestion", None))


@mcp.tool(
    title="Create Folder",
    description="Create a folder inside the allowed roots.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
async def files_create_folder(path: str, ctx: Context) -> FileMutationResponse | ErrorResponse:
    try:
        ensure_action_allowed("files_create_folder")
        created = _bridge().create_folder(path)
        await ctx.session.send_resource_list_changed()
        return FileMutationResponse(path=created, action="created")
    except (SafetyError, FilesBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, getattr(exc, "suggestion", None))


@mcp.tool(
    title="Move Path",
    description="Move or rename a file or folder inside the allowed roots.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
async def files_move_path(source: str, destination: str, ctx: Context) -> FileMutationResponse | ErrorResponse:
    try:
        ensure_action_allowed("files_move_path")
        original, moved = _bridge().move_path(source=source, destination=destination)
        await ctx.session.send_resource_list_changed()
        return FileMutationResponse(path=original, destination=moved, action="moved")
    except (SafetyError, FilesBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, getattr(exc, "suggestion", None))


@mcp.tool(
    title="Delete Path",
    description="Delete a file or empty folder inside the allowed roots. Requires full_access safety mode.",
    annotations=ToolAnnotations(destructiveHint=True, idempotentHint=True, openWorldHint=False),
    structured_output=True,
)
async def files_delete_path(path: str, ctx: Context) -> FileMutationResponse | ErrorResponse:
    try:
        ensure_action_allowed("files_delete_path")
        deleted = _bridge().delete_path(path)
        await ctx.session.send_resource_list_changed()
        return FileMutationResponse(path=deleted, action="deleted")
    except (SafetyError, FilesBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, getattr(exc, "suggestion", None))


def _serialize_prompt_messages(messages: list[object]) -> list[dict[str, object]]:
    return [
        {
            "role": getattr(message, "role", "user"),
            "content": message.content.model_dump(mode="json") if hasattr(message.content, "model_dump") else message.content,
        }
        for message in messages
    ]


@mcp.tool(
    title="Files List Prompts",
    description="Fallback prompt discovery tool for tool-only MCP clients.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
async def files_list_prompts() -> dict[str, object]:
    prompts = await mcp.list_prompts()
    return {
        "ok": True,
        "prompts": [{"name": prompt.name, "title": prompt.title, "description": prompt.description} for prompt in prompts],
        "count": len(prompts),
    }


@mcp.tool(
    title="Files Get Prompt",
    description="Fallback prompt rendering tool for tool-only MCP clients.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
async def files_get_prompt_prompt(name: str, arguments_json: str | None = None) -> dict[str, object]:
    arguments = json.loads(arguments_json) if arguments_json else None
    prompt = await mcp.get_prompt(name, arguments)
    return {"ok": True, "name": name, "messages": _serialize_prompt_messages(prompt.messages), "message_count": len(prompt.messages)}


@mcp._mcp_server.subscribe_resource()
async def _files_subscribe_resource(uri) -> None:
    del uri


@mcp._mcp_server.unsubscribe_resource()
async def _files_unsubscribe_resource(uri) -> None:
    del uri


TOOL_DISCOVERY = install_search_first_discovery(
    mcp,
    server_name="Apple Files MCP",
    domain="files",
)


def main() -> None:
    settings = load_settings()
    if settings.transport == "stdio":
        mcp.run(transport="stdio")
        return
    mcp.settings.host = settings.host
    mcp.settings.port = settings.port
    mcp.settings.log_level = settings.log_level
    mcp.settings.stateless_http = True
    mcp.settings.json_response = True
    mcp.run(transport="streamable-http")
