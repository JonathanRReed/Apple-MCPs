# Apple Calendar

Apple Calendar access for AI agents on macOS.

This MCP lets an agent list calendars, read events, create events, update events, and delete events while keeping Calendar as the system of record.

## Use This Server When

- you want a calendar-only assistant
- you want EventKit-backed calendar access without the all-in-one server
- you want tighter app-level separation for scheduling workflows

## What This MCP Gives An Agent

- calendar discovery
- event listing and detail
- event create, update, and delete
- today resources and planning prompts
- health output that distinguishes empty results from blocked Calendar access
- `calendar_permission_guide` and `calendar_recheck_permissions` for permission recovery

## Install On This Mac

<details>
<summary>Quick start</summary>

```bash
cd /Users/jonathanreed/Downloads/Apple-MCPs/Apple-Calendar-MCP
./start.sh
```

On first run, `start.sh` creates `.venv`, installs `requirements.txt`, and starts the server over `stdio`.

</details>

## Install In AI Agents

<details>
<summary>Generic MCP client config</summary>

```json
{
  "mcpServers": {
    "apple-calendar": {
      "command": "/Users/jonathanreed/Downloads/Apple-MCPs/Apple-Calendar-MCP/start.sh",
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
  -- /Users/jonathanreed/Downloads/Apple-MCPs/Apple-Calendar-MCP/start.sh
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
- Add `/Users/jonathanreed/Downloads/Apple-MCPs/Apple-Calendar-MCP/start.sh` to your MCP client
- Reload or reconnect the client so the Calendar tool surface is loaded into context
- Call `calendar_health` first
- If access is blocked or `access_status` is `not_determined`, call `calendar_permission_guide`
- After changing macOS permissions, call `calendar_recheck_permissions`

## Related

- [Apple-Tools-MCP](../Apple-Tools-MCP/README.md)
