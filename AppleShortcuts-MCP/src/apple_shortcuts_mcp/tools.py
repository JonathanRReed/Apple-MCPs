from __future__ import annotations

import json
import logging
from typing import Annotated

from mcp.server.mcpserver import Context
from mcp.types import Annotations, InputRequiredResult, PromptMessage, ToolAnnotations
from pydantic import Field

from apple_mcp_common.discovery import install_search_first_discovery
from apple_mcp_common.runtime import notify_resources_changed, python_log_level, require_loopback_host
from apple_mcp_common.safety import safety_mode_warning
from apple_mcp_common.server import AppleMCPServer
from apple_shortcuts_mcp.config import Settings, load_settings
from apple_shortcuts_mcp.models import ErrorResponse, HealthResponse, ShortcutFolderListResponse, ShortcutListResponse, ShortcutPermissionStatus, ShortcutRunResponse, ToolError, ViewShortcutResponse
from apple_shortcuts_mcp.permissions import SAFETY_ENV_VAR, SafetyError, ensure_action_allowed
from apple_shortcuts_mcp.shortcuts_bridge import ShortcutsBridge, ShortcutsBridgeError

SERVER_INSTRUCTIONS = (
    "Use this server for Apple Shortcuts on macOS. "
    "Search here when the user wants to discover shortcuts, inspect shortcut metadata, browse folders, or run a shortcut. "
    "Prefer list and view before run when shortcut identity is uncertain."
)

_SHORTCUT_DESCRIPTION = (
    "Exact shortcut name (case-insensitive when unambiguous) or its identifier (UUID) from shortcuts_list_shortcuts. "
    "Use the identifier when several shortcuts share a name."
)
_FOLDER_NAME_DESCRIPTION = "Optional Shortcuts folder name from shortcuts_list_folders. Omit to list every shortcut."
_PROMPT_NAME_DESCRIPTION = "Prompt name from shortcuts_list_prompts."
_PROMPT_ARGUMENTS_DESCRIPTION = "Optional JSON object string of prompt arguments, for example '{\"topic\": \"work\"}'."

mcp = AppleMCPServer("Apple Shortcuts MCP", instructions=SERVER_INSTRUCTIONS, version=load_settings().version)


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(level=python_log_level(settings.log_level))


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
        safety_mode_warning=safety_mode_warning(SAFETY_ENV_VAR, settings.safety_mode),
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
    input_text: str | None = None,
) -> ShortcutRunResponse:
    return _bridge().run_shortcut(
        shortcut_name_or_identifier,
        input_paths=input_paths,
        output_path=output_path,
        output_type=output_type,
        input_text=input_text,
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
    annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
    structured_output=True,
)
def shortcuts_health() -> HealthResponse:
    return health_tool(load_settings())


@mcp.tool(
    title="Shortcuts Permission Guide",
    description="Explain the runtime requirements for Apple Shortcuts on macOS.",
    annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
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
    annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=False, open_world_hint=False),
    structured_output=True,
)
async def shortcuts_refresh_state(ctx: Context) -> HealthResponse:
    await ctx.report_progress(25, 100, "Refreshing Shortcuts state")
    response = shortcuts_health()
    await notify_resources_changed(ctx)
    await ctx.report_progress(100, 100, "Done")
    return response


@mcp.tool(
    title="List Shortcuts",
    description="List Apple Shortcuts, optionally restricted to one folder.",
    annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
    structured_output=True,
)
def shortcuts_list_shortcuts(
    folder_name: Annotated[str | None, Field(description=_FOLDER_NAME_DESCRIPTION)] = None,
) -> ShortcutListResponse | ErrorResponse:
    try:
        ensure_action_allowed("shortcuts_list_shortcuts")
        return shortcuts_list_shortcuts_tool(folder_name=folder_name)
    except (SafetyError, ShortcutsBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="List Shortcut Folders",
    description="List Apple Shortcuts folders.",
    annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
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
    annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
    structured_output=True,
)
def shortcuts_view_shortcut(
    shortcut_name_or_identifier: Annotated[str, Field(description=_SHORTCUT_DESCRIPTION)],
) -> ViewShortcutResponse | ErrorResponse:
    try:
        ensure_action_allowed("shortcuts_view_shortcut")
        return shortcuts_view_shortcut_tool(shortcut_name_or_identifier)
    except (SafetyError, ShortcutsBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Run Shortcut",
    description="Run a shortcut by name or identifier with optional input and output arguments.",
    annotations=ToolAnnotations(destructive_hint=True, idempotent_hint=False, open_world_hint=True),
    structured_output=True,
)
def shortcuts_run_shortcut(
    shortcut_name_or_identifier: Annotated[str, Field(description=_SHORTCUT_DESCRIPTION)],
    input_paths: Annotated[
        list[str] | None,
        Field(description="Optional absolute paths of files to pass to the shortcut as input, in order."),
    ] = None,
    output_path: Annotated[
        str | None,
        Field(description="Optional absolute file path where the shortcut's output is written. Omit to get the output as text."),
    ] = None,
    output_type: Annotated[
        str | None,
        Field(description="Optional Uniform Type Identifier for the output, such as public.plain-text or public.png."),
    ] = None,
    input_text: Annotated[
        str | None,
        Field(description="Optional text passed to the shortcut as its input."),
    ] = None,
) -> ShortcutRunResponse | ErrorResponse:
    try:
        ensure_action_allowed("shortcuts_run_shortcut")
        return shortcuts_run_shortcut_tool(
            shortcut_name_or_identifier,
            input_paths=input_paths,
            output_path=output_path,
            output_type=output_type,
            input_text=input_text,
        )
    except (SafetyError, ShortcutsBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


def _serialize_prompt_messages(messages: list[PromptMessage]) -> list[dict[str, object]]:
    return [
        {
            "role": getattr(message, "role", "user"),
            "content": message.content.model_dump(mode="json") if hasattr(message.content, "model_dump") else message.content,
        }
        for message in messages
    ]


@mcp.tool(
    title="Shortcuts List Prompts",
    description="Fallback prompt discovery tool for tool-only MCP clients.",
    annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
    structured_output=True,
)
async def shortcuts_list_prompts() -> dict[str, object]:
    prompts = await mcp.list_prompts()
    return {
        "ok": True,
        "prompts": [{"name": prompt.name, "title": prompt.title, "description": prompt.description} for prompt in prompts],
        "count": len(prompts),
    }


@mcp.tool(
    name="shortcuts_get_prompt",
    title="Shortcuts Get Prompt",
    description="Fallback prompt rendering tool for tool-only MCP clients.",
    annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
    structured_output=True,
)
async def shortcuts_get_prompt_prompt(
    name: Annotated[str, Field(description=_PROMPT_NAME_DESCRIPTION)],
    arguments_json: Annotated[str | None, Field(description=_PROMPT_ARGUMENTS_DESCRIPTION)] = None,
) -> dict[str, object]:
    arguments = json.loads(arguments_json) if arguments_json else None
    prompt = await mcp.get_prompt(name, arguments)
    if isinstance(prompt, InputRequiredResult):
        return {"ok": False, "name": name, "error": {"error_code": "PROMPT_INPUT_REQUIRED", "message": f"Prompt '{name}' needs client input before it can render."}}
    return {"ok": True, "name": name, "messages": _serialize_prompt_messages(prompt.messages), "message_count": len(prompt.messages)}


TOOL_DISCOVERY = install_search_first_discovery(
    mcp,
    server_name="Apple Shortcuts MCP",
    domain="shortcuts",
)


def main() -> None:
    settings = load_settings()
    configure_logging(settings)
    if settings.transport == "stdio":
        mcp.run(transport="stdio")
        return
    mcp.run(
        transport="streamable-http",
        host=require_loopback_host(settings.host),
        port=settings.port,
        stateless_http=False,
        json_response=True,
    )
