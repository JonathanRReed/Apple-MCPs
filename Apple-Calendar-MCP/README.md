<!-- mcp-name: io.github.jonathanrreed/apple-calendar-mcp -->

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
- Tool discovery helpers `search_tools` and `get_tool_info` for context-constrained clients
- Today resources and planning prompts
- Health checks that distinguish empty results from blocked access
- Read fallback through Calendar.app automation when native EventKit reads are blocked on supported local setups
- Permission recovery: `calendar_permission_guide`, `calendar_recheck_permissions`

## Install On This Mac

<details>
<summary>Quick start (uvx, from PyPI)</summary>

With [uv](https://docs.astral.sh/uv/getting-started/installation/) installed:

```bash
uvx apple-calendar-mcp
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

This builds one workspace environment with every server's entry point in `.venv/bin` (for example `.venv/bin/apple-calendar-mcp`). You can also point an MCP client at `Apple-Calendar-MCP/start.sh`, which prefers `uv run` and falls back to a plain venv bootstrap (Python 3.11+ required).

</details>

## Install In AI Agents

<details>
<summary>Generic MCP client config</summary>

```json
{
  "mcpServers": {
    "apple-calendar": {
      "command": "uvx",
      "args": ["apple-calendar-mcp"],
      "env": {
        "APPLE_CALENDAR_MCP_SAFETY_MODE": "safe_manage"
      }
    }
  }
}
```

Running from a clone instead? Use `/path/to/Apple-MCPs/Apple-Calendar-MCP/start.sh` as the command with empty `args`.

</details>

<details>
<summary>Claude Code example</summary>

```bash
claude mcp add --transport stdio --scope project apple-calendar -- uvx apple-calendar-mcp
```

</details>

## Safety Modes

- `safe_readonly`
- `safe_manage`
- `full_access`

## Transport

`stdio` is the default and recommended transport. Set `APPLE_CALENDAR_MCP_TRANSPORT=streamable-http` (with optional `APPLE_CALENDAR_MCP_HOST` and `APPLE_CALENDAR_MCP_PORT`) to serve Streamable HTTP instead.

## macOS Permissions

- Calendar access is required
- `calendar_health` reports `access_status`, read access, and write access so agents can detect blocked permissions before treating an empty window as real data

## Launch Checklist

- Add `uvx apple-calendar-mcp` (or a clone's `Apple-Calendar-MCP/start.sh`) to your MCP client
- Reload or reconnect the client so the Calendar tool surface is loaded into context
- Call `calendar_health` first
- If access is blocked or `access_status` is `not_determined`, call `calendar_permission_guide`
- After changing macOS permissions, call `calendar_recheck_permissions`

## Prompting Notes

- `tools/list` returns the full Calendar tool surface. Context-constrained clients can use `search_tools` first, then `get_tool_info` for the Calendar tool they need.
- Before creating events, confirm the date, time, duration, and title with the user
- Use Calendar for scheduled time blocks, meetings, and appointments

## Related

- [Apple-Tools-MCP](../Apple-Tools-MCP/README.md)
