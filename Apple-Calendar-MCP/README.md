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

## Bridge Batch Lookup

The internal Python `CalendarBridge.get_events(event_ids)` method batches native lookups without adding an MCP tool. Pass a sequence of non-empty strings, at most 10000 input IDs. Duplicate input IDs are resolved once. Requests are chunked to an exact 32768-byte UTF-8 JSON argv budget, including JSON escaping; an individual oversized ID is rejected before any lookup.

The returned mapping distinguishes:
- An event value: a validated response for the requested ID
- None: an explicit native miss confirmed through the existing single-get/JXA fallback, or a definitive miss on that fallback path
- An absent key: unknown, including unanswered, malformed, contradictory, duplicate-response, mismatched, or unsupported entries

JXA-issued IDs are opaque versioned tokens that identify the Automation backend, calendar scope, and exact UID or id() namespace/value. Do not parse or construct them. UID-less events keep their actual typed id() value; distinct events with identical metadata no longer collapse. Rows without usable identifiers, or duplicate provider identities, receive display-only weak tokens. Weak tokens cannot prove absence or authorize writes.

Versioned tokens resolve directly through verified, server-filtered JXA lookups. A single matching calendar and event are required; ambiguous, unavailable, malformed, or mismatched lookups remain unknown. No unfiltered event-directory scan is used. Lookup snapshots are capped at 1000 calendars and 1000 returned matches per query, and identifiers at 32768 characters. Legacy bare UID/id values still resolve when their namespaces unambiguously identify the same event. Legacy calendar/start/title composites remain readable when unique, but cannot authorize mutations or definitive batch absence. Legacy values that resemble versioned tokens are rejected if their meanings conflict.

Native misses retry the single-get/JXA path. If the whole native batch cannot answer, a fallback miss for an opaque native ID remains unknown because JXA may use a different identifier format. A verified versioned JXA miss can establish absence. Permission or per-ID confirmation failures remain unknown; non-fallback whole-helper transport failures remain explicit errors. A valid native reply with a different canonical ID requires a separate single-get lookup confirming that canonical ID. Conflicting or unconfirmed aliases remain unknown. Unsupported legacy `uid:` IDs remain unknown without a lookup. Callers must not delete mappings for absent keys.

JXA in-place updates and deletion require a strong, unique identity and reject stale calendar names before writing. Calendar moves through the JXA fallback are explicitly unsupported because cloning cannot safely preserve every event field. Native Calendar moves remain available. Recurrence updates through versioned JXA IDs are also unsupported.

The native batch command itself reports EventKit-only lookup outcomes. Synthetic IDs produce UNSUPPORTED_IDENTIFIER; native EVENT_NOT_FOUND alone is not a confirmed absence across both backends.

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

### Event alerts

`calendar_create_event` and `calendar_update_event` accept `alarms`: an array of `{ "minutes_before": 15 }` or `{ "absolute_iso": "2030-10-11T10:00:00Z" }` objects. Relative offsets must be whole minutes from 0 through 525600; each event accepts at most 100 alarms. Omit `alarms` to preserve existing alerts on update, or pass `[]` to clear them.

Event detail and list responses include alarm metadata. EventKit reports relative, absolute, and location alerts. The Calendar scripting fallback creates display alerts and reads the alert types exposed by Calendar's scripting dictionary. It refuses replacement when an event has an open-file alert, which current macOS versions do not allow scripts to modify.

Thanks to LightSpeedSpirit for the original event-alarm contribution in [PR #26](https://github.com/JonathanRReed/Apple-MCPs/pull/26).
