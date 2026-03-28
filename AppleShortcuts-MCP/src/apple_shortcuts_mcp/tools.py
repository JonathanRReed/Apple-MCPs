from __future__ import annotations

import json
import logging

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import Annotations, ToolAnnotations

from apple_shortcuts_mcp.config import Settings, load_settings
from apple_shortcuts_mcp.models import ErrorResponse, HealthResponse, ShortcutFolderListResponse, ShortcutListResponse, ShortcutPermissionStatus, ShortcutRunResponse, ToolError, ViewShortcutResponse
from apple_shortcuts_mcp.permissions import SafetyError, ensure_action_allowed
from apple_shortcuts_mcp.shortcuts_bridge import ShortcutsBridge, ShortcutsBridgeError

SERVER_INSTRUCTIONS = (
    "Use this server for Apple Shortcuts on macOS. "
    "Search here when the user wants to discover shortcuts, inspect shortcut metadata, browse folders, or run a shortcut. "
    "Prefer list and view before run when shortcut identity is uncertain."
)

mcp = FastMCP("Apple Shortcuts MCP", instructions=SERVER_INSTRUCTIONS, json_response=True)


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))


def _bridge() -> ShortcutsBridge:
    settings = load_settings()
    return ShortcutsBridge(shortcuts_command=settings.shortcuts_command, timeout_seconds=settings.command_timeout_seconds)


def _error_response(error_code: str, message: str, suggestion: str | None = None) -> ErrorResponse:
    return ErrorResponse(error=ToolError(error_code=error_code, message=message, suggestion=suggestion))


def _resource_json(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, default=str)


def health_tool(settings: Settings) -> HealthResponse:
    bridge = ShortcutsBridge(shortcuts_command=settings.shortcuts_command, timeout_seconds=settings.command_timeout_seconds)
    return HealthResponse(
        ok=True,
        server_name=settings.server_name,
        version=settings.version,
        safety_mode=settings.safety_mode,
        transport=settings.transport,
        capabilities=[
            "list_shortcuts",
            "list_folders",
            "view_shortcuts",
            "run_shortcuts",
            "resources",
            "prompts",
        ],
        permissions=ShortcutPermissionStatus(
            shortcuts_cli_available=bridge.cli_available(),
            shortcuts_command=settings.shortcuts_command,
            command_timeout_seconds=settings.command_timeout_seconds,
        ),
        transport_support=["stdio", "streamable-http"],
    )


def shortcuts_list_shortcuts_tool(folder_name: str | None = None) -> ShortcutListResponse:
    shortcuts = _bridge().list_shortcuts(folder_name=folder_name)
    return ShortcutListResponse(shortcuts=shortcuts, count=len(shortcuts))


def shortcuts_list_folders_tool() -> ShortcutFolderListResponse:
    folders = _bridge().list_folders()
    return ShortcutFolderListResponse(folders=folders, count=len(folders))


def shortcuts_view_shortcut_tool(shortcut_name_or_identifier: str) -> ViewShortcutResponse:
    shortcut = _bridge().view_shortcut(shortcut_name_or_identifier)
    return ViewShortcutResponse(ok=True, shortcut=shortcut, opened=True)


def shortcuts_run_shortcut_tool(
    shortcut_name_or_identifier: str,
    input_paths: list[str] | None = None,
    output_path: str | None = None,
    output_type: str | None = None,
) -> ShortcutRunResponse:
    return _bridge().run_shortcut(
        shortcut_name_or_identifier,
        input_paths=input_paths,
        output_path=output_path,
        output_type=output_type,
    )


@mcp.resource(
    "shortcuts://all",
    name="shortcuts_all",
    title="All Shortcuts",
    description="Current Apple Shortcuts folders and shortcuts.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.9),
)
def shortcuts_all_resource() -> str:
    return _resource_json(_bridge().shortcuts_snapshot())


@mcp.resource(
    "shortcuts://folder/{folder_name}",
    name="shortcuts_folder",
    title="Shortcuts Folder",
    description="Shortcuts in a specific Apple Shortcuts folder.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.8),
)
def shortcuts_folder_resource(folder_name: str) -> str:
    return _resource_json(_bridge().shortcuts_folder_snapshot(folder_name))


@mcp.prompt(name="shortcuts_choose_and_run", title="Choose and Run Shortcut")
def shortcuts_choose_and_run_prompt() -> str:
    return (
        "Find the best existing Apple Shortcut for the user's task, confirm the shortcut identity, "
        "and run it with the right inputs. Summarize the result and include the output if one is produced."
    )


@mcp.prompt(name="shortcuts_run_with_input", title="Run Shortcut With Structured Input")
def shortcuts_run_with_input_prompt() -> str:
    return (
        "Run a chosen Apple Shortcut with structured inputs, input files, or an output path if needed. "
        "Prefer a named or identified shortcut over an ambiguous name."
    )


@mcp.prompt(name="shortcuts_follow_up", title="Use Shortcut Output")
def shortcuts_follow_up_prompt() -> str:
    return (
        "Use the output of a recently run Apple Shortcut in a follow-up task. "
        "Inspect the shortcut output, then continue the user's workflow."
    )


@mcp.tool(
    title="Shortcuts Health",
    description="Report the active Apple Shortcuts MCP configuration.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def shortcuts_health() -> HealthResponse:
    return health_tool(load_settings())


@mcp.tool(
    title="Shortcuts Permission Guide",
    description="Explain the runtime requirements for Apple Shortcuts on macOS.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def shortcuts_permission_guide() -> dict[str, object]:
    return {
        "ok": True,
        "domain": "shortcuts",
        "can_prompt_in_app": False,
        "requires_manual_system_settings": False,
        "steps": [
            "Ensure the `shortcuts` CLI is available on this Mac.",
            "Use list or run tools from this MCP server.",
        ],
    }


@mcp.tool(
    title="Shortcuts Refresh State",
    description="Refresh Shortcuts resources and notify the client that the shortcut catalog may have changed.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=False),
    structured_output=True,
)
async def shortcuts_refresh_state(ctx: Context) -> HealthResponse:
    await ctx.report_progress(25, 100, "Refreshing Shortcuts state")
    response = shortcuts_health()
    await ctx.session.send_resource_list_changed()
    await ctx.report_progress(100, 100, "Done")
    return response


@mcp.tool(
    title="List Shortcuts",
    description="List Apple Shortcuts, optionally restricted to one folder.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def shortcuts_list_shortcuts(folder_name: str | None = None) -> ShortcutListResponse | ErrorResponse:
    try:
        ensure_action_allowed("shortcuts_list_shortcuts")
        return shortcuts_list_shortcuts_tool(folder_name=folder_name)
    except (SafetyError, ShortcutsBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="List Shortcut Folders",
    description="List Apple Shortcuts folders.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def shortcuts_list_folders() -> ShortcutFolderListResponse | ErrorResponse:
    try:
        ensure_action_allowed("shortcuts_list_folders")
        return shortcuts_list_folders_tool()
    except (SafetyError, ShortcutsBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="View Shortcut",
    description="Open a shortcut in the Shortcuts app by name or identifier and return its metadata.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def shortcuts_view_shortcut(shortcut_name_or_identifier: str) -> ViewShortcutResponse | ErrorResponse:
    try:
        ensure_action_allowed("shortcuts_view_shortcut")
        return shortcuts_view_shortcut_tool(shortcut_name_or_identifier)
    except (SafetyError, ShortcutsBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Run Shortcut",
    description="Run a shortcut by name or identifier with optional input and output arguments.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def shortcuts_run_shortcut(
    shortcut_name_or_identifier: str,
    input_paths: list[str] | None = None,
    output_path: str | None = None,
    output_type: str | None = None,
) -> ShortcutRunResponse | ErrorResponse:
    try:
        ensure_action_allowed("shortcuts_run_shortcut")
        return shortcuts_run_shortcut_tool(
            shortcut_name_or_identifier,
            input_paths=input_paths,
            output_path=output_path,
            output_type=output_type,
        )
    except (SafetyError, ShortcutsBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


def main() -> None:
    settings = load_settings()
    configure_logging(settings)
    if settings.transport == "stdio":
        mcp.run(transport="stdio")
        return
    mcp.run(
        transport="streamable-http",
        host=settings.host,
        port=settings.port,
        stateless_http=True,
        json_response=True,
    )
