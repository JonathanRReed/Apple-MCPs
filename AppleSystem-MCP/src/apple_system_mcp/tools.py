from __future__ import annotations

import json

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import Annotations, ToolAnnotations

from apple_system_mcp.config import load_settings
from apple_system_mcp.models import ClipboardResponse, ErrorResponse, GuiActionResponse, GuiMenuItemsResponse, HealthResponse, NotificationResponse, OpenAppResponse, PreferenceDomainResponse, RunningAppsResponse, SettingMutationResponse, SettingsDomainsResponse, SettingsSectionResponse, SettingsSnapshotResponse, StatusResponse, ToolError
from apple_system_mcp.permissions import SafetyError, ensure_action_allowed
from apple_system_mcp.system_bridge import SystemBridgeError, build_bridge

SERVER_INSTRUCTIONS = (
    "Use this server for macOS system context. "
    "Search here when the user wants battery state, the frontmost app, running applications, the clipboard, local notifications, application launch, or a read-only view of macOS settings and preference domains."
)

mcp = FastMCP("Apple System MCP", instructions=SERVER_INSTRUCTIONS, json_response=True)


def _bridge():
    return build_bridge()


def _error_response(error_code: str, message: str, suggestion: str | None = None) -> ErrorResponse:
    return ErrorResponse(error=ToolError(error_code=error_code, message=message, suggestion=suggestion))


def _resource_json(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, default=str)


def _setting_mutation_response(section: str, setting: str, payload: dict[str, object], used_gui_fallback: bool = False) -> SettingMutationResponse:
    return SettingMutationResponse(
        section=section,
        setting=setting,
        requested_value=payload["requested_value"],
        observed_value=payload.get("observed_value"),
        restarted_processes=list(payload.get("restarted_processes", [])),
        used_gui_fallback=used_gui_fallback,
    )


def _gui_action_response(action: str, application: str | None, target: str | None = None, value: bool | str | list[str] | None = None) -> GuiActionResponse:
    return GuiActionResponse(action=action, application=application, target=target, value=value)


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


@mcp.resource(
    "system://settings",
    name="system_settings",
    title="System Settings Snapshot",
    description="A read-only snapshot of appearance, accessibility, Dock, and Finder settings.",
    mime_type="application/json",
    annotations=Annotations(audience=["assistant"], priority=0.78),
)
def system_settings_resource() -> str:
    return _resource_json(_bridge().settings_snapshot())


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
            "list_settings_domains",
            "get_appearance_settings",
            "get_accessibility_settings",
            "get_dock_settings",
            "get_finder_settings",
            "get_settings_snapshot",
            "read_preference_domain",
            "set_appearance_mode",
            "set_show_all_extensions",
            "set_show_hidden_files",
            "set_finder_path_bar",
            "set_finder_status_bar",
            "set_dock_autohide",
            "set_dock_show_recents",
            "set_reduce_motion",
            "set_increase_contrast",
            "set_reduce_transparency",
            "set_clipboard",
            "show_notification",
            "open_application",
            "gui_list_menu_bar_items",
            "gui_click_menu_path",
            "gui_press_keys",
            "gui_type_text",
            "gui_click_button",
            "gui_choose_popup_value",
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
            "GUI fallback tools require Accessibility access for the host app in System Settings -> Privacy & Security -> Accessibility.",
            "Settings inspection tools read macOS preference domains through the defaults system.",
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
    title="List Settings Domains",
    description="List the common macOS preference domains exposed by Apple System MCP.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def system_list_settings_domains() -> SettingsDomainsResponse | ErrorResponse:
    try:
        ensure_action_allowed("system_list_settings_domains")
        domains = _bridge().list_settings_domains()
        return SettingsDomainsResponse(domains=domains, count=len(domains))
    except (SafetyError, SystemBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Get Appearance Settings",
    description="Read current macOS appearance settings such as light or dark mode and accent color.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def system_get_appearance_settings() -> SettingsSectionResponse | ErrorResponse:
    try:
        ensure_action_allowed("system_get_appearance_settings")
        return SettingsSectionResponse(section="appearance", values=_bridge().appearance_settings())
    except (SafetyError, SystemBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Get Accessibility Settings",
    description="Read common macOS accessibility settings such as reduce motion and increase contrast.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def system_get_accessibility_settings() -> SettingsSectionResponse | ErrorResponse:
    try:
        ensure_action_allowed("system_get_accessibility_settings")
        return SettingsSectionResponse(section="accessibility", values=_bridge().accessibility_settings())
    except (SafetyError, SystemBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Get Dock Settings",
    description="Read common macOS Dock settings such as autohide, magnification, and orientation.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def system_get_dock_settings() -> SettingsSectionResponse | ErrorResponse:
    try:
        ensure_action_allowed("system_get_dock_settings")
        return SettingsSectionResponse(section="dock", values=_bridge().dock_settings())
    except (SafetyError, SystemBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Get Finder Settings",
    description="Read common macOS Finder settings such as path bar, status bar, and preferred view style.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def system_get_finder_settings() -> SettingsSectionResponse | ErrorResponse:
    try:
        ensure_action_allowed("system_get_finder_settings")
        return SettingsSectionResponse(section="finder", values=_bridge().finder_settings())
    except (SafetyError, SystemBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Get Settings Snapshot",
    description="Return a combined read-only snapshot of appearance, accessibility, Dock, and Finder settings.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def system_get_settings_snapshot() -> SettingsSnapshotResponse | ErrorResponse:
    try:
        ensure_action_allowed("system_get_settings_snapshot")
        snapshot = _bridge().settings_snapshot()
        return SettingsSnapshotResponse(
            appearance=snapshot["appearance"],
            accessibility=snapshot["accessibility"],
            dock=snapshot["dock"],
            finder=snapshot["finder"],
        )
    except (SafetyError, SystemBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Read Preference Domain",
    description="Read a macOS preference domain through defaults export for a production-safe, structured settings view.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    structured_output=True,
)
def system_read_preference_domain(domain: str, current_host: bool = False) -> PreferenceDomainResponse | ErrorResponse:
    try:
        ensure_action_allowed("system_read_preference_domain")
        return PreferenceDomainResponse(
            domain=domain,
            current_host=current_host,
            values=_bridge().read_preference_domain(domain, current_host=current_host),
        )
    except (SafetyError, SystemBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Set Appearance Mode",
    description="Set macOS appearance mode to light or dark.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def system_set_appearance_mode(mode: str) -> SettingMutationResponse | ErrorResponse:
    try:
        ensure_action_allowed("system_set_appearance_mode")
        return _setting_mutation_response("appearance", "mode", _bridge().set_appearance_mode(mode))
    except (SafetyError, SystemBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Set Show All Extensions",
    description="Show or hide filename extensions in macOS.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def system_set_show_all_extensions(enabled: bool) -> SettingMutationResponse | ErrorResponse:
    try:
        ensure_action_allowed("system_set_show_all_extensions")
        return _setting_mutation_response("appearance", "show_all_extensions", _bridge().set_show_all_extensions(enabled))
    except (SafetyError, SystemBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Set Show Hidden Files",
    description="Show or hide hidden files in Finder.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def system_set_show_hidden_files(enabled: bool) -> SettingMutationResponse | ErrorResponse:
    try:
        ensure_action_allowed("system_set_show_hidden_files")
        return _setting_mutation_response("finder", "show_hidden_files", _bridge().set_show_hidden_files(enabled))
    except (SafetyError, SystemBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Set Finder Path Bar",
    description="Show or hide the Finder path bar.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def system_set_finder_path_bar(enabled: bool) -> SettingMutationResponse | ErrorResponse:
    try:
        ensure_action_allowed("system_set_finder_path_bar")
        return _setting_mutation_response("finder", "show_path_bar", _bridge().set_finder_path_bar(enabled))
    except (SafetyError, SystemBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Set Finder Status Bar",
    description="Show or hide the Finder status bar.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def system_set_finder_status_bar(enabled: bool) -> SettingMutationResponse | ErrorResponse:
    try:
        ensure_action_allowed("system_set_finder_status_bar")
        return _setting_mutation_response("finder", "show_status_bar", _bridge().set_finder_status_bar(enabled))
    except (SafetyError, SystemBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Set Dock Autohide",
    description="Enable or disable Dock autohide.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def system_set_dock_autohide(enabled: bool) -> SettingMutationResponse | ErrorResponse:
    try:
        ensure_action_allowed("system_set_dock_autohide")
        return _setting_mutation_response("dock", "autohide", _bridge().set_dock_autohide(enabled))
    except (SafetyError, SystemBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Set Dock Show Recents",
    description="Enable or disable recent applications in the Dock.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def system_set_dock_show_recents(enabled: bool) -> SettingMutationResponse | ErrorResponse:
    try:
        ensure_action_allowed("system_set_dock_show_recents")
        return _setting_mutation_response("dock", "show_recents", _bridge().set_dock_show_recents(enabled))
    except (SafetyError, SystemBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Set Reduce Motion",
    description="Enable or disable macOS reduce motion accessibility mode.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def system_set_reduce_motion(enabled: bool) -> SettingMutationResponse | ErrorResponse:
    try:
        ensure_action_allowed("system_set_reduce_motion")
        return _setting_mutation_response("accessibility", "reduce_motion", _bridge().set_reduce_motion(enabled))
    except (SafetyError, SystemBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Set Increase Contrast",
    description="Enable or disable macOS increase contrast accessibility mode.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def system_set_increase_contrast(enabled: bool) -> SettingMutationResponse | ErrorResponse:
    try:
        ensure_action_allowed("system_set_increase_contrast")
        return _setting_mutation_response("accessibility", "increase_contrast", _bridge().set_increase_contrast(enabled))
    except (SafetyError, SystemBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Set Reduce Transparency",
    description="Enable or disable macOS reduce transparency accessibility mode.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=False),
    structured_output=True,
)
def system_set_reduce_transparency(enabled: bool) -> SettingMutationResponse | ErrorResponse:
    try:
        ensure_action_allowed("system_set_reduce_transparency")
        return _setting_mutation_response("accessibility", "reduce_transparency", _bridge().set_reduce_transparency(enabled))
    except (SafetyError, SystemBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="List Menu Bar Items",
    description="List the top-level menu bar items for an application. This is a GUI fallback tool.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=True, openWorldHint=True),
    structured_output=True,
)
def system_gui_list_menu_bar_items(application: str | None = None) -> GuiMenuItemsResponse | ErrorResponse:
    try:
        ensure_action_allowed("system_gui_list_menu_bar_items")
        app_name = application or _bridge().frontmost_app()
        items = _bridge().gui_list_menu_bar_items(application=app_name)
        return GuiMenuItemsResponse(application=app_name, menu_bar_items=items, count=len(items))
    except (SafetyError, SystemBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Click Menu Path",
    description="Click a menu path in an application, for example ['File', 'New Window']. This is a GUI fallback tool.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=True),
    structured_output=True,
)
def system_gui_click_menu_path(menu_path: list[str], application: str | None = None) -> GuiActionResponse | ErrorResponse:
    try:
        ensure_action_allowed("system_gui_click_menu_path")
        app_name = _bridge().gui_click_menu_path(menu_path=menu_path, application=application)
        return _gui_action_response("click_menu_path", application=app_name, target=" > ".join(menu_path), value=menu_path)
    except (SafetyError, SystemBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Press Keys",
    description="Press a key or key chord in the target application. This is a GUI fallback tool.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=True),
    structured_output=True,
)
def system_gui_press_keys(key: str, modifiers: list[str] | None = None, application: str | None = None) -> GuiActionResponse | ErrorResponse:
    try:
        ensure_action_allowed("system_gui_press_keys")
        app_name = _bridge().gui_press_keys(key=key, modifiers=modifiers, application=application)
        value: bool | str | list[str] | None = key
        if modifiers:
            value = [key, *modifiers]
        return _gui_action_response("press_keys", application=app_name, target=key, value=value)
    except (SafetyError, SystemBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Type Text",
    description="Type text into the frontmost focused control. This is a GUI fallback tool.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=True),
    structured_output=True,
)
def system_gui_type_text(text: str, application: str | None = None) -> GuiActionResponse | ErrorResponse:
    try:
        ensure_action_allowed("system_gui_type_text")
        app_name = _bridge().gui_type_text(text=text, application=application)
        return _gui_action_response("type_text", application=app_name, value=text)
    except (SafetyError, SystemBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Click Button",
    description="Click a named button in the frontmost window. This is a GUI fallback tool.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=True),
    structured_output=True,
)
def system_gui_click_button(label: str, application: str | None = None) -> GuiActionResponse | ErrorResponse:
    try:
        ensure_action_allowed("system_gui_click_button")
        app_name = _bridge().gui_click_button(label=label, application=application)
        return _gui_action_response("click_button", application=app_name, target=label, value=label)
    except (SafetyError, SystemBridgeError) as exc:
        return _error_response(exc.error_code, exc.message, exc.suggestion)


@mcp.tool(
    title="Choose Pop-Up Value",
    description="Choose a value from a named pop-up button in the frontmost window. This is a GUI fallback tool.",
    annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False, openWorldHint=True),
    structured_output=True,
)
def system_gui_choose_popup_value(label: str, value: str, application: str | None = None) -> GuiActionResponse | ErrorResponse:
    try:
        ensure_action_allowed("system_gui_choose_popup_value")
        app_name = _bridge().gui_choose_popup_value(label=label, value=value, application=application)
        return _gui_action_response("choose_popup_value", application=app_name, target=label, value=value)
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
