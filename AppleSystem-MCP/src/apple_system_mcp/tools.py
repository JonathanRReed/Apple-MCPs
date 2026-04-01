from __future__ import annotations

import json

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import Annotations, ToolAnnotations

from apple_system_mcp.config import load_settings
from apple_system_mcp.models import ClipboardResponse, ErrorResponse, HealthResponse, NotificationResponse, OpenAppResponse, RunningAppsResponse, StatusResponse, ToolError
from apple_system_mcp.permissions import SafetyError, ensure_action_allowed
from apple_system_mcp.system_bridge import SystemBridgeError, build_bridge

SERVER_INSTRUCTIONS = (
    "Use this server for macOS system context. "
    "Search here when the user wants battery state, the frontmost app, running applications, the clipboard, a local notification, or to open an application."
)

mcp = FastMCP("Apple System MCP", instructions=SERVER_INSTRUCTIONS, json_response=True)


def _bridge():
    return build_bridge()


def _error_response(error_code: str, message: str, suggestion: str | None = None) -> ErrorResponse:
    return ErrorResponse(error=ToolError(error_code=error_code, message=message, suggestion=suggestion))


def _resource_json(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, default=str)


@mcp.resource(
    "system://status",
    name="system_status",
    title="System Status",
    description="A compact macOS system status snapshot.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.8),
)
def system_status_resource() -> str:
    bridge = _bridge()
    payload = {
        "battery": bridge.battery().model_dump(),
        "frontmost_app": bridge.frontmost_app(),
        "running_apps_count": len(bridge.running_apps()),
    }
    return _resource_json(payload)


@mcp.resource(
    "system://applications",
    name="system_applications",
    title="Running Applications",
    description="Currently running foreground applications on macOS.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.7),
)
def system_applications_resource() -> str:
    apps = _bridge().running_apps()
    return _resource_json({"apps": [item.model_dump() for item in apps], "count": len(apps)})


@mcp.prompt(name="system_capture_context", title="Capture System Context")
def system_capture_context_prompt() -> str:
    return (
        "Use Apple System MCP to capture the current desktop context before acting. "
        "Check the frontmost app, battery status, and running applications when that helps route the next action."
    )


@mcp.tool(
    title="System Health",
    description="Report the active Apple System MCP configuration.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def system_health() -> HealthResponse:
    settings = load_settings()
    return HealthResponse(
        server_name=settings.server_name,
        version=settings.version,
        safety_mode=settings.safety_mode,
        transport=settings.transport,
        capabilities=[
            "status",
            "get_battery",
            "get_frontmost_app",
            "list_running_apps",
            "get_clipboard",
            "set_clipboard",
            "show_notification",
            "open_application",
            "resources",
            "prompts",
        ],
        supports=["stdio", "streamable-http"],
    )


@mcp.tool(
    title="System Permission Guide",
    description="Explain what system access this MCP may need on macOS.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def system_permission_guide() -> dict[str, object]:
    settings = load_settings()
    return {
        "ok": True,
        "domain": "system",
        "can_prompt_in_app": True,
        "requires_manual_system_settings": False,
        "steps": [
            "Read-only system tools usually work without a prompt.",
            "If System Events prompts for permission, approve the macOS automation request.",
            "If clipboard or notification behavior is blocked, re-open the host app after granting access.",
        ],
        "notes": [f"Current safety mode: {settings.safety_mode}"],
    }


@mcp.tool(
    title="System Status",
    description="Return current battery, frontmost app, and running app count.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def system_status() -> StatusResponse | ErrorResponse:
    try:
        ensure_action_allowed("system_status")
        bridge = _bridge()
        apps = bridge.running_apps()
        return StatusResponse(
            battery=bridge.battery(),
            frontmost_app=bridge.frontmost_app(),
            running_apps_count=len(apps),
        )
    except (SafetyError, SystemBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Get Battery",
    description="Get the current battery state from macOS.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def system_get_battery() -> dict[str, object] | ErrorResponse:
    try:
        ensure_action_allowed("system_get_battery")
        return {"ok": True, "battery": _bridge().battery().model_dump()}
    except (SafetyError, SystemBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Get Frontmost App",
    description="Get the name of the current frontmost application.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def system_get_frontmost_app() -> dict[str, object] | ErrorResponse:
    try:
        ensure_action_allowed("system_get_frontmost_app")
        return {"ok": True, "application": _bridge().frontmost_app()}
    except (SafetyError, SystemBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="List Running Apps",
    description="List currently running foreground applications.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def system_list_running_apps() -> RunningAppsResponse | ErrorResponse:
    try:
        ensure_action_allowed("system_list_running_apps")
        apps = _bridge().running_apps()
        return RunningAppsResponse(apps=apps, count=len(apps))
    except (SafetyError, SystemBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Get Clipboard",
    description="Read the current text clipboard contents.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def system_get_clipboard() -> ClipboardResponse | ErrorResponse:
    try:
        ensure_action_allowed("system_get_clipboard")
        return ClipboardResponse(text=_bridge().get_clipboard())
    except (SafetyError, SystemBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Set Clipboard",
    description="Write text into the macOS clipboard.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def system_set_clipboard(text: str) -> ClipboardResponse | ErrorResponse:
    try:
        ensure_action_allowed("system_set_clipboard")
        _bridge().set_clipboard(text)
        return ClipboardResponse(text=text)
    except (SafetyError, SystemBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Show Notification",
    description="Display a local macOS notification.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=True),
    structured_output=True,
)
def system_show_notification(title: str, body: str, subtitle: str | None = None) -> NotificationResponse | ErrorResponse:
    try:
        ensure_action_allowed("system_show_notification")
        _bridge().show_notification(title=title, body=body, subtitle=subtitle)
        return NotificationResponse(delivered=True, title=title)
    except (SafetyError, SystemBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Open Application",
    description="Open an application by name using macOS.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=True),
    structured_output=True,
)
async def system_open_application(application: str, ctx: Context) -> OpenAppResponse | ErrorResponse:
    try:
        ensure_action_allowed("system_open_application")
        _bridge().open_application(application)
        await ctx.session.send_resource_list_changed()
        return OpenAppResponse(opened=True, application=application)
    except (SafetyError, SystemBridgeError) as exc:
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
    title="System List Prompts",
    description="Fallback prompt discovery tool for tool-only MCP clients.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
async def system_list_prompts() -> dict[str, object]:
    prompts = await mcp.list_prompts()
    return {
        "ok": True,
        "prompts": [{"name": prompt.name, "title": prompt.title, "description": prompt.description} for prompt in prompts],
        "count": len(prompts),
    }


@mcp.tool(
    title="System Get Prompt",
    description="Fallback prompt rendering tool for tool-only MCP clients.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
async def system_get_prompt_prompt(name: str, arguments_json: str | None = None) -> dict[str, object]:
    arguments = json.loads(arguments_json) if arguments_json else None
    prompt = await mcp.get_prompt(name, arguments)
    return {"ok": True, "name": name, "messages": _serialize_prompt_messages(prompt.messages), "message_count": len(prompt.messages)}


@mcp._mcp_server.subscribe_resource()
async def _system_subscribe_resource(uri) -> None:
    del uri


@mcp._mcp_server.unsubscribe_resource()
async def _system_unsubscribe_resource(uri) -> None:
    del uri


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
