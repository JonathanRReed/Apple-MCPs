<!-- mcp-name: io.github.JonathanRReed/apple-calendar-mcp -->

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
- Set event alarms (reminders) when creating or updating an event
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

## Event Alarms

`calendar_create_event` and `calendar_update_event` take an optional `alarms` parameter: a list of objects, each with **exactly one** of

- `minutes_before` — a whole number of minutes before the event start, from 0 through 525600 (one year); `15` means "alert 15 minutes before"
- `absolute_iso` — an ISO datetime for a fixed alert time

```json
{
  "title": "Design review",
  "start_iso": "2026-08-30T14:00:00",
  "end_iso": "2026-08-30T15:00:00",
  "calendar_id": "...",
  "alarms": [{ "minutes_before": 15 }, { "absolute_iso": "2026-08-30T09:00:00" }]
}
```

Semantics:

- On create, omitting `alarms` creates the event with no alarms.
- On update, omitting `alarms` leaves the event's existing alarms unchanged; passing `[]` clears them all. There is no partial add or remove — the list you pass replaces the event's alarms.
- Native get/create/update detail responses return structured alarm records. Relative alarms have `type: "relative"` and signed `offset_minutes` (for example, -15); absolute alarms have `type: "absolute"` and `absolute`; location alarms have `type: "location"`, `proximity`, and `location_title`. Location alarms are read-only through these tools. Their offset is a raw EventKit value, not a guaranteed travel-time estimate. Nonfinite or unrepresentable external offsets are omitted.
- List responses remain event summaries and do not include alarms. The automation fallback cannot read alarms, so its detail responses return alarms as null rather than implying an empty list. Native detail responses return [] when no alarms exist.
- Any provided alarms list, including `[]`, requires native EventKit support. If the helper cannot service the mutation, the request returns `UNSUPPORTED_OPERATION` before any automation fallback write. Omitting alarms preserves existing fallback behavior.
- At most 100 alarms are accepted. Python and Swift both validate the range and shape before saving.
- An entry with both fields, neither field, a negative `minutes_before`, or an unparseable `absolute_iso` is rejected with `INVALID_INPUT` before any calendar write happens.

## Safety Modes

- `safe_readonly`
- `safe_manage`
- `full_access`

### Calendar allowlists

Set these environment variables in your MCP client's configuration, then restart the server:

| Variable | Effect |
| --- | --- |
| `APPLE_CALENDAR_MCP_ALLOWED_CALENDARS` | Comma-separated calendar names the server may read or modify. Calendar listings, event listings, event details, and Calendar resources respect this scope. |
| `APPLE_CALENDAR_MCP_WRITE_ALLOWED_CALENDARS` | Additional comma-separated calendar names the server may create, update, or delete events in. It does not hide other readable calendars. |

For an assistant that may read your schedule but only write to a dedicated calendar:

```json
{
  "APPLE_CALENDAR_MCP_SAFETY_MODE": "safe_manage",
  "APPLE_CALENDAR_MCP_WRITE_ALLOWED_CALENDARS": "AI Planning"
}
```

Leaving either allowlist unset or empty applies no restriction from that list. When both are set, writes must pass both; `safe_readonly` blocks all writes regardless of either list. Moving an event checks both the source and destination calendar. A write with an unresolved target is rejected when an allowlist is configured.

Names are exact, case-sensitive matches after trimming configuration whitespace. Every calendar with a matching name is included, so use unique calendar names for security-sensitive scopes. `calendar_health` reports the configured write allowlist.

These are policies enforced by the Python MCP server, not a macOS sandbox. Direct use of the native helper or bridge library does not enforce them. macOS permissions still apply, and your MCP client may send returned data to its model provider.

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
