# Troubleshooting

Answers for the questions macOS permissions generate. If an issue is not
covered here, please open a bug report — the template asks for the health
tool output, which is the fastest way to diagnose anything below.

## Start with the health tools

Every server exposes diagnostic tools; call them before anything else:

- `<server>_health` (for example `notes_health`, `calendar_health`) reports
  version, safety mode, and capability state.
- `<server>_permission_guide` explains exactly which macOS permission is
  missing and how to grant it.
- `<server>_recheck_permissions` re-probes after you change a setting, so you
  don't need to restart the client.

## Automation permission prompts (all servers)

The AppleScript-backed servers (Notes, Mail, Messages, and the Calendar
fallback) need **Automation** consent, and macOS grants it to the *host
application* that runs the server — Terminal, Claude Desktop, your IDE — not
to the server itself.

- The prompt appears once, on first use. If it was dismissed or denied:
  System Settings → Privacy & Security → **Automation** → find the host app →
  enable the target app (Notes, Calendar, ...).
- Running the same server from a different host app triggers a fresh prompt —
  that is expected.
- To force the prompt to reappear: `tccutil reset AppleEvents` (resets
  Automation consent for all apps, so other tools will re-prompt too).

## Calendar: "Add Only" access behaves differently

macOS offers two grant levels for Calendar (System Settings → Privacy &
Security → **Calendars**): Full Access and **Add Only**. Under Add Only the
native EventKit helper cannot read calendars or events, so the server
transparently falls back to AppleScript:

- Everything works (list, get, create, update, delete), but calendar ids are
  calendar **names** and event ids are AppleScript uids rather than EventKit
  identifiers. Treat ids as opaque and short-lived: list first, then act.
- `calendar_access_status` shows the current tier (`can_read_events` /
  `can_write_events`). For full-fidelity ids and faster operations, grant
  Full Access.

## Notes: timeouts and the create-note guarantee

Notes.app can stall mid-request while syncing (especially iCloud accounts).
Every AppleScript call the Notes server makes is bounded by
`APPLE_NOTES_MCP_SCRIPT_TIMEOUT_SECONDS` (default `60`, minimum `5`), so a
stalled request returns a structured error instead of hanging your client.

For `notes_create_note` specifically — creation is not idempotent, so the
server never leaves you guessing:

- If Notes committed the note but stalled afterwards, the server recovers it
  by title lookup and returns success with the note id.
- If the outcome genuinely cannot be verified, you get
  `NOTE_CREATE_STATUS_UNKNOWN`. **Do not retry blindly** — list notes in the
  target folder and check for the title first, otherwise you may create a
  duplicate.

## Common error codes

| Code | Meaning | What to do |
| --- | --- | --- |
| `PERMISSION_DENIED` | macOS blocked automation or data access | Call `<server>_permission_guide`, grant the permission, then `<server>_recheck_permissions` |
| `APPLESCRIPT_TIMEOUT` | The target app stalled past the deadline | The app may be busy or syncing; verify state before retrying a mutation |
| `NOTE_CREATE_STATUS_UNKNOWN` | Create timed out and could not be verified | Check the target folder for the title before creating again |
| `CALENDAR_NOT_FOUND` / `EVENT_NOT_FOUND` | Id did not resolve | List calendars/events first — ids change shape under Add Only access |

## Still stuck?

Open an issue with the health tool output and the exact error payload. Please
do not include note bodies, event details, or other personal content —
error codes and tool names are enough to diagnose almost everything.
