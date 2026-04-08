# Apple System MCP

Local MCP server for macOS system context, truthful Focus support metadata, assistant-relevant settings reads, explicit settings writes, and bounded GUI fallback automation.

## Capabilities

- battery status
- frontmost app
- running applications
- clipboard read and write
- local notifications
- open an application
- appearance settings
- accessibility settings
- Dock settings
- Finder settings
- truthful Focus support metadata
- combined system context snapshots
- appearance mode write
- Finder visibility and bar writes
- Dock write controls for autohide and recent apps
- accessibility writes for reduce motion, increase contrast, and reduce transparency
- GUI fallback tools for menu clicks, key presses, text entry, button clicks, and pop-up selection
- preference-domain inspection via `defaults export`
- resources: `system://status`, `system://applications`, `system://settings`, `system://context`
- prompt: `system_capture_context`
- search-first discovery through `search_tools` and `get_tool_info`

## Install On This Mac

<details>
<summary>Quick start</summary>

```bash
cd /path/to/Apple-MCPs/AppleSystem-MCP
./start.sh
```

`start.sh` bootstraps and repairs `.venv` as needed, reinstalls when `requirements.txt` changes, and starts the server over `stdio`.

</details>

## Install In AI Agents

```json
{
  "mcpServers": {
    "apple-system": {
      "command": "/path/to/Apple-MCPs/AppleSystem-MCP/start.sh",
      "args": [],
      "env": {
        "APPLE_SYSTEM_MCP_SAFETY_MODE": "safe_manage"
      }
    }
  }
}
```

## Prompting Notes

- `tools/list` is intentionally minimal. Use `search_tools` first, then `get_tool_info` for the deferred System tool you need.
- Use this server when the user’s current desktop context matters.
- Read battery state and the frontmost app before interruptive actions.
- Use the settings tools before falling back to raw `defaults read` in prompts or E2E checks.
- Use `APPLE_SYSTEM_MCP_SAFETY_MODE=safe_manage` for assistant-grade operation.
- Keep `safe_readonly` only for audit-only or context-only deployments.
- Keep GUI fallback narrow. Prefer native app-domain MCPs first, then explicit System tools, then GUI tools only when native support is missing.
- Focus reporting is best-effort and truthful. This server does not claim Notification Center history support when macOS does not expose it cleanly on an unsigned local install.

## Health And Recovery

- `system_health`
- `system_permission_guide`
- `system_get_settings_snapshot`
- `system_get_focus_status`
- `system_get_context_snapshot`
- `system_read_preference_domain`

## Assistant-Grade Control Surface

The launch System write surface is explicit, not generic:

- `system_set_appearance_mode`
- `system_set_show_all_extensions`
- `system_set_show_hidden_files`
- `system_set_finder_path_bar`
- `system_set_finder_status_bar`
- `system_set_dock_autohide`
- `system_set_dock_show_recents`
- `system_set_reduce_motion`
- `system_set_increase_contrast`
- `system_set_reduce_transparency`

The bounded GUI fallback surface is:

- `system_gui_list_menu_bar_items`
- `system_gui_click_menu_path`
- `system_gui_press_keys`
- `system_gui_type_text`
- `system_gui_click_button`
- `system_gui_choose_popup_value`

## Launch Checklist

- Start the server once with `./start.sh`
- Add `/path/to/Apple-MCPs/AppleSystem-MCP/start.sh` to your MCP client
- Reload or reconnect the client so the System tool surface is loaded into context
- Call `system_health` first
- If a scoped system action is blocked, call `system_permission_guide`
- Call `system_status` to verify the full context surface is available
