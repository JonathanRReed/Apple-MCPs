<!-- mcp-name: io.github.JonathanRReed/apple-system-mcp -->

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
- tool discovery helpers `search_tools` and `get_tool_info` for context-constrained clients

## Install On This Mac

<details>
<summary>Quick start (uvx, from PyPI)</summary>

With [uv](https://docs.astral.sh/uv/getting-started/installation/) installed:

```bash
uvx apple-system-mcp
```

No clone, no venv management.

</details>

<details>
<summary>From a clone</summary>

```bash
git clone https://github.com/JonathanRReed/Apple-MCPs.git
cd Apple-MCPs
uv sync --all-packages
```

This builds one workspace environment with every server's entry point in `.venv/bin` (for example `.venv/bin/apple-system-mcp`). You can also point an MCP client at `AppleSystem-MCP/start.sh`, which prefers `uv run` and falls back to a plain venv bootstrap (Python 3.11+ required).

</details>

## Install In AI Agents

```json
{
  "mcpServers": {
    "apple-system": {
      "command": "uvx",
      "args": ["apple-system-mcp"],
      "env": {
        "APPLE_SYSTEM_MCP_SAFETY_MODE": "safe_manage"
      }
    }
  }
}
```

Running from a clone instead? Use `/path/to/Apple-MCPs/AppleSystem-MCP/start.sh` as the command with empty `args`.

Claude Code:

```bash
claude mcp add --transport stdio --scope project apple-system -- uvx apple-system-mcp
```

## Transport

`stdio` is the default and recommended transport. Set `APPLE_SYSTEM_MCP_TRANSPORT=streamable-http` (with optional `APPLE_SYSTEM_MCP_HOST` and `APPLE_SYSTEM_MCP_PORT`) to serve Streamable HTTP instead.

## Prompting Notes

- `tools/list` returns the full System tool surface. Context-constrained clients can use `search_tools` first, then `get_tool_info` for the System tool they need.
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

- Add `uvx apple-system-mcp` (or a clone's `AppleSystem-MCP/start.sh`) to your MCP client
- Reload or reconnect the client so the System tool surface is loaded into context
- Call `system_health` first
- If a scoped system action is blocked, call `system_permission_guide`
- Call `system_status` to verify the full context surface is available
