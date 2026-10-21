"""Shared wording for macOS privacy (TCC) guidance about the native helpers."""

from apple_mcp_common.native import HelperBundle


def helper_permission_guide(domain: str, pane: str, tcc_service: str, helper: HelperBundle) -> dict[str, object]:
    """Explain how a Swift helper gets access to a TCC-protected service.

    ``pane`` is the System Settings > Privacy & Security pane name and
    ``tcc_service`` the name ``tccutil`` accepts for that service.
    """
    return {
        "ok": True,
        "domain": domain,
        "can_prompt_in_app": True,
        "requires_manual_system_settings": False,
        "helper_name": helper.display_name,
        "helper_bundle_identifier": helper.bundle_identifier,
        "steps": [
            f"Call any {pane} tool from this MCP server. If the app running the server (for example Claude, Terminal or an editor) already has {pane} access, that access is used and nothing else is needed.",
            f"Otherwise macOS asks whether '{helper.display_name}' may access {pane}. Choose Allow. The prompt can open behind other windows.",
            f"If a tool still returns PERMISSION_DENIED, open System Settings > Privacy & Security > {pane} and turn on '{helper.display_name}', or the app named in the error.",
            f"If neither is listed, run `tccutil reset {tcc_service} {helper.bundle_identifier}` in Terminal, then call a {pane} tool again to get a new prompt.",
        ],
        "notes": [
            f"macOS checks the app that started this MCP server first. Apps whose Info.plist has no {pane} usage description cannot show a {pane} prompt and are never listed in System Settings, so the helper asks in its own name instead.",
            "An update that changes the helper's Swift source rebuilds and re-signs it. macOS may then ask once more for the helper.",
        ],
    }
