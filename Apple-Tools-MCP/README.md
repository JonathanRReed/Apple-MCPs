# Apple-Tools-MCP

Unified MCP server for Apple apps on macOS.

One entrypoint for Mail, Calendar, Reminders, Messages, Contacts, Notes, Shortcuts, Files, System, and Maps. This server wraps the standalone servers and exposes a unified MCP interface.

## What It Does

- Read context across multiple Apple apps
- Unified actions across all apps
- Prompts for day planning, communications triage, and meeting prep
- Persistent defaults for mail, calendar, reminders, notes, and communication routing
- Per-contact preferences for people who always route a specific way
- Helper workflows for communication routing, archiving mail, capturing follow-ups, and collaboration summaries
- Mail thread helpers and Contacts method editing in one place
- Preview, audit, and undo for reversible actions
- Files-aware attachment and document workflows within scoped roots
- System-aware workflows using the frontmost app, clipboard, notifications, running apps, and assistant-relevant macOS settings
- Explicit macOS settings writes for appearance, Finder, Dock, and key accessibility preferences
- Bounded GUI fallback tools when a native app-domain MCP cannot complete a task directly
- Travel-aware workflows using Apple Maps for place search and route estimates
- Long-running briefing and triage tools for clients that support MCP tasks
- Prompt fallback via `apple_list_prompts` and `apple_get_prompt`
- One install target instead of ten separate configurations

## When to use

- Personal assistant workflows across multiple Apple apps
- Cross-app operations (e.g., Calendar and Reminders together)
- Simpler setup without wiring each standalone MCP separately

## Install On This Mac

<details>
<summary>Quick start</summary>

```bash
cd /path/to/Apple-MCPs/Apple-Tools-MCP
./start.sh
```

On first run, `start.sh` creates `.venv`, installs `requirements.txt`, and starts the MCP server over `stdio`.

</details>

<details>
<summary>Install all Apple MCP packages into one shared environment</summary>

```bash
cd /path/to/Apple-MCPs
bash scripts/install_all.sh
```

This installs `Apple-Tools-MCP` plus every standalone package into one environment. Use this path when you want the unified server to import installed domain packages directly instead of relying on the monorepo fallback.

</details>

## Install In AI Agents

<details>
<summary>Generic MCP client config</summary>

```json
{
  "mcpServers": {
    "apple-tools": {
      "command": "/path/to/Apple-MCPs/Apple-Tools-MCP/start.sh",
      "args": [],
      "env": {
        "APPLE_MAIL_MCP_SAFETY_PROFILE": "full_access",
        "APPLE_CALENDAR_MCP_SAFETY_MODE": "safe_manage",
        "APPLE_REMINDERS_MCP_SAFETY_MODE": "safe_manage",
        "APPLE_FILES_MCP_ALLOWED_ROOTS": "/Users/you/Desktop,/Users/you/Documents,/Users/you/Downloads",
        "APPLE_FILES_MCP_SAFETY_MODE": "safe_readonly",
        "APPLE_SYSTEM_MCP_SAFETY_MODE": "safe_readonly",
        "APPLE_CONTACTS_MCP_SAFETY_MODE": "safe_readonly",
        "APPLE_NOTES_MCP_SAFETY_MODE": "full_access",
        "APPLE_MESSAGES_MCP_SAFETY_MODE": "full_access",
        "APPLE_SHORTCUTS_MCP_SAFETY_MODE": "full_access"
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
  apple-tools \
  -- /path/to/Apple-MCPs/Apple-Tools-MCP/start.sh
```

</details>

## What It Exposes

- Health and overview tools across all apps
- Cross-app prompts
- Delegated tools from Mail, Calendar, Reminders, Messages, Contacts, Notes, Shortcuts, Files, System, and Maps
- Suggestions and permission guides
- Files, System, and Maps resources and prompts
- Preference tools: get, detect, and update defaults and contact preferences
- Communication tools: prepare, send, preview
- Workflow tools: archive, create reminders and notes with defaults, preview those defaulted writes, capture follow-ups, preview follow-up capture, and summarize event collaboration
- Audit tools: list recent actions and undo
- Briefing tools: daily, weekly, and communications triage (with task support)
- Prompt fallback: `apple_list_prompts` and `apple_get_prompt`
- Mail thread tools: get, reply, archive
- Contacts mutation: create, update, delete with labeled methods
- Calendar and Messages permission diagnostics
- Launch and recovery: `apple_health`, `apple_permission_guide`, `apple_recheck_permissions`

## Assistant Defaults

Apple-Tools-MCP can persist a lightweight assistant state file with defaults for:

- default mail account
- default archive mailbox
- default calendar
- default reminders list
- default notes folder
- preferred communication channel, `messages`, `mail`, or `auto`
- preferred message target type, `phone`, `email`, or `auto`
- per-contact preferred channel and target overrides for specific people

Detect and persist sensible defaults with `apple_detect_defaults`, inspect them with `apple_get_preferences`, and override them with `apple_update_preferences`.

By default the state file is stored at `~/.apple-tools-mcp/preferences.json`. Override it with `APPLE_AGENT_MCP_STATE_FILE`.

Apple-Tools-MCP also stores recent assistant actions in `~/.apple-tools-mcp/actions.json` so the unified server can expose audit history and undo for reversible operations.

## How to Work With It

- Resolve people through Contacts first, then decide between Messages or Mail based on saved defaults.
- Set per-contact preferences for people who always prefer a specific channel.
- Preview risky actions and defaulted create flows when the client wants confirmation.
- Use Mail thread helpers when the user refers to a conversation, not a single message.
- Set defaults early (archive mailbox, calendar, reminders list, notes folder) so the assistant doesn't keep asking.
- Keep contact info current so communication routing works reliably.
- Use Files before Mail, Messages, Notes, or Shortcuts when the request involves local documents.
- Check System context before interruptive actions, especially when the frontmost app, clipboard, or battery state matters.
- Prefer explicit System settings tools over generic GUI automation when the request is really a macOS preference change.
- Use GUI fallback tools only when the native domain MCP cannot complete the task and the client has granted Accessibility access.
- Use Maps when routing or travel time affects scheduling or communication.
- Use `apple_list_recent_actions` and `apple_undo_action` for reversible operations.

## macOS Permissions

- Mail needs Automation access to Mail
- Calendar needs Calendar access
- Reminders needs Reminders access
- Messages needs Automation access to Messages, plus Full Disk Access for history
- Contacts needs Contacts access
- Notes needs Automation access to Notes
- Shortcuts usually works without a separate privacy prompt
- Files access is controlled by `APPLE_FILES_MCP_ALLOWED_ROOTS`, not by a macOS privacy prompt
- System actions may trigger System Events, Accessibility, or automation prompts depending on the host app
- Maps does not need a privacy prompt, but search and directions require the local Swift helper to compile

## Launch Checklist

- Start the server once with `./start.sh`
- Add `/path/to/Apple-MCPs/Apple-Tools-MCP/start.sh` to your MCP client
- Reload or reconnect the client so the Apple-Tools-MCP tool surface is loaded into context
- Call `apple_health` first to verify every domain
- If a domain is blocked, call `apple_permission_guide`
- After changing macOS permissions, call `apple_recheck_permissions`

## Protocol Verification

Normal agent setups should use `stdio`. For protocol validation, Apple-Tools-MCP also supports `streamable-http`.

### Official MCP conformance

Start Apple-Tools-MCP in conformance mode:

```bash
cd /path/to/Apple-MCPs/Apple-Tools-MCP
APPLE_AGENT_MCP_TRANSPORT=streamable-http \
APPLE_AGENT_MCP_PORT=8765 \
APPLE_AGENT_MCP_CONFORMANCE_MODE=1 \
./start.sh
```

Then run the official active suite:

```bash
npx -y @modelcontextprotocol/conformance server \
  --url http://127.0.0.1:8765/mcp \
  --suite active
```

`APPLE_AGENT_MCP_CONFORMANCE_MODE=1` adds an opt-in MCP conformance surface for tools, prompts, resources, completion, logging, progress, sampling, and elicitation. It is intended for CI and protocol testing, not normal assistant use.

Apple-Tools-MCP also enables experimental MCP task support in normal operation. The task-capable briefing and triage tools advertise `taskSupport=optional`, so task-aware clients can run them asynchronously while direct clients can still call them normally.

## Launch Docs

- [Golden Workflows](../docs/launch/golden-workflows.md)
- [Failure Modes](../docs/launch/failure-modes.md)
- [Compatibility and Version Pinning](../docs/launch/compatibility.md)
- [Demo Script](../docs/launch/demo-script.md)
- [Checklist Template Prompt](../docs/launch/prompts/checklist-template.md)

### Inspector CLI smoke check

From this server directory:

```bash
npx -y @modelcontextprotocol/inspector --cli bash ./start.sh --method tools/list
npx -y @modelcontextprotocol/inspector --cli bash ./start.sh --method prompts/list
npx -y @modelcontextprotocol/inspector --cli bash ./start.sh --method resources/list
```

For the full repo-wide smoke pass, run:

```bash
cd /path/to/Apple-MCPs
bash scripts/inspector_smoke.sh
```

## Agent Routing Prompt

```xml
<apple_tools>
All Apple tools are deferred. Batch tool_search calls on first use.

<routing>
  <imessage trigger="text, message, msg, iMessage">
    Resolve recipient via Contacts first. Confirm if multiple matches.
    Omit service_name parameter entirely.
  </imessage>

  <contacts trigger="lookup, phone number, email, contact">
    Run before any iMessage or Mail action.
  </contacts>

  <mail trigger="email, mail, inbox, draft, reply">
    Search requires a query string (sender, subject, or "*" as wildcard). No list-all endpoint.
    If text vs. email is ambiguous, ask once.
  </mail>

  <calendar trigger="calendar, event, schedule, appointment, meeting, block time">
    Confirm date, time, duration, and title before writing.
  </calendar>

  <reminders trigger="remind me, task, to-do, don't forget">
    Reminders are organized into lists. Identify available lists on first use and set a default.
    due_date requires timezone offset: yyyy-MM-ddTHH:mm:ss-HH:00
  </reminders>

  <notes trigger="note, jot down, write this down, save this">
    Multiple accounts may have a "Notes" folder. Identify them on first use and set a default.
    Use for reference only. Time-sensitive items go to Reminders or Calendar.
  </notes>

  <shortcuts trigger="shortcut, automation, run shortcut">
    List available shortcuts before running if request is vague.
  </shortcuts>

  <files trigger="file, folder, attachment, document, download, desktop">
    Use Files before Mail, Messages, Notes, or Shortcuts when the request references local paths or attachments.
    Confirm the exact path before mutation or send actions.
  </files>

  <system trigger="clipboard, frontmost app, battery, notification, open app">
    Use System when local desktop context affects the next action.
    Keep writes scoped unless the user clearly asked for a notification, clipboard update, or app launch.
  </system>

  <maps trigger="map, directions, route, commute, eta, address, place">
    Use Maps when place lookup or travel time affects scheduling or communication.
    Confirm origin, destination, and transport mode for time-sensitive plans.
  </maps>
</routing>

<disambiguation>
  1. Has due date/time -> Reminders
  2. Reference material, no action -> Notes
  3. Involves another person -> iMessage or Mail (Contacts first)
  4. Text vs. email unclear -> ask once
</disambiguation>

<known_gotchas>
  - service_name on iMessage calls causes error (-1728). Omit it.
  - Bare timestamps without timezone offset fail on Reminders.
  - Mail has no "list recent" endpoint. Always pass a search query.
  - All tool schemas are deferred. First call requires tool_search to load parameters.
  - Multiple Notes folders exist across accounts. Pick one default.
  - Files access is limited to APPLE_FILES_MCP_ALLOWED_ROOTS.
  - Some System actions depend on host app automation approval.
  - Maps search and directions depend on the local Swift helper and Xcode command line tools.
</known_gotchas>
</apple_tools>
```

## Related Servers

- [Apple Files MCP](../AppleFiles-MCP/README.md)
- [Apple System MCP](../AppleSystem-MCP/README.md)
- [Apple Maps MCP](../AppleMaps-MCP/README.md)
- [Apple Mail MCP](../AppleMail-MCP/README.md)
- [Apple Calendar](../Apple-Calendar-MCP/README.md)
- [Apple Reminders MCP](../AppleReminders-MCP/README.md)
- [Apple Messages MCP](../AppleMessages-MCP/README.md)
- [Apple Contacts MCP](../AppleContacts-MCP/README.md)
- [Apple Notes MCP](../AppleNotes-MCP/README.md)
- [Apple Shortcuts MCP](../AppleShortcuts-MCP/README.md)
