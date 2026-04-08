# Apple Calendar

MCP server for Apple Calendar on macOS.

Provides access to calendars and events through EventKit. Keep Calendar as the system of record while enabling agents to read, create, update, and delete events.

## When to use

- Calendar-only workflows
- EventKit-backed calendar access without the all-in-one server
- Tighter app-level separation for scheduling

## What It Does

- Discover and list calendars
- Create, read, update, and delete events
- Search-first discovery through `search_tools` and `get_tool_info`
- Today resources and planning prompts
- Health checks that distinguish empty results from blocked access
- Read fallback through Calendar.app automation when native EventKit reads are blocked on supported local setups
- Permission recovery: `calendar_permission_guide`, `calendar_recheck_permissions`

## Install On This Mac

<details>
<summary>Quick start</summary>

```bash
cd /path/to/Apple-MCPs/Apple-Calendar-MCP
./start.sh
```

`start.sh` bootstraps and repairs `.venv` as needed, reinstalls when `requirements.txt` changes, and starts the server over `stdio`.

</details>

## Install In AI Agents

<details>
<summary>Generic MCP client config</summary>

```json
{
  "mcpServers": {
    "apple-calendar": {
      "command": "/path/to/Apple-MCPs/Apple-Calendar-MCP/start.sh",
      "args": [],
      "env": {
        "APPLE_CALENDAR_MCP_SAFETY_MODE": "safe_manage"
      }
    }
  }
}
```

</details>

<details>
<summary>Claude Code example</summary>

```bash
claude mcp add --transport stdio --scope project \
  apple-calendar \
  -- /path/to/Apple-MCPs/Apple-Calendar-MCP/start.sh
```

</details>

## Safety Modes

- `safe_readonly`
- `safe_manage`
- `full_access`

## macOS Permissions

- Calendar access is required
- `calendar_health` reports `access_status`, read access, and write access so agents can detect blocked permissions before treating an empty window as real data

## Launch Checklist

- Start the server once with `./start.sh`
- Add `/path/to/Apple-MCPs/Apple-Calendar-MCP/start.sh` to your MCP client
- Reload or reconnect the client so the Calendar tool surface is loaded into context
- Call `calendar_health` first
- If access is blocked or `access_status` is `not_determined`, call `calendar_permission_guide`
- After changing macOS permissions, call `calendar_recheck_permissions`

## Prompting Notes

- `tools/list` is intentionally minimal. Use `search_tools` first, then `get_tool_info` for the deferred Calendar tool you need.
- Before creating events, confirm the date, time, duration, and title with the user
- Use Calendar for scheduled time blocks, meetings, and appointments

## Related

- [Apple-Tools-MCP](../Apple-Tools-MCP/README.md)
