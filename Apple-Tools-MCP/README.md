# Apple-Tools-MCP

Unified MCP server for Apple apps on macOS.

One entrypoint for Mail, Calendar, Reminders, Messages, Contacts, Notes, Shortcuts, Files, System, and Maps. This server wraps the standalone servers in this repository and exposes a unified MCP interface.

## Capabilities

- Cross-app context reading
- Unified action interface across all apps
- Cross-app prompts for day planning, communications triage, and meeting prep
- Persistent assistant defaults for mail, calendar, reminders, notes, and communication routing
- Per-contact communication preferences for people who should always route a specific way
- Cross-app helper workflows for communication routing, archiving mail, capturing follow-ups, and collaboration summaries
- Unified access to Mail thread helpers and Contacts method editing from one server
- Preview, audit, and undo helpers for reversible assistant actions
- Files-aware attachment and document workflows inside scoped local roots
- System-aware workflows that can use the frontmost app, clipboard, notifications, and running apps
- Travel-aware workflows that can search places and estimate routes with Apple Maps
- Task-capable long-running briefing and triage tools for clients that support MCP tasks
- Tool-only prompt fallback through `apple_list_prompts` and `apple_get_prompt`
- Single install target instead of ten separate configurations

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

- aggregated health and overview tools
- cross-app prompts
- the delegated Mail, Calendar, Reminders, Messages, Contacts, Notes, Shortcuts, Files, System, and Maps tools
- Apple-wide suggestion and permission-guide tools
- delegated Files, System, and Maps resources and prompts
- assistant preference tools: `apple_get_preferences`, `apple_detect_defaults`, `apple_update_preferences`, `apple_update_contact_preferences`
- assistant routing tools: `apple_prepare_communication`, `apple_send_communication`
- assistant preview tools: `apple_preview_communication`, `apple_preview_archive_message`
- assistant workflow tools: `apple_archive_message`, `apple_create_reminder_with_defaults`, `apple_create_note_with_defaults`, `apple_capture_follow_up_from_mail`, `apple_event_collaboration_summary`
- assistant audit tools: `apple_list_recent_actions`, `apple_undo_action`
- task-capable assistant tools: `apple_generate_daily_briefing`, `apple_generate_weekly_briefing`, `apple_triage_communications_task`
- prompt fallback tools: `apple_list_prompts`, `apple_get_prompt`
- delegated Mail thread tools: `mail_get_thread`, `mail_reply_latest_in_thread`, `mail_archive_thread`
- delegated Contacts mutation tools with labeled methods: `contacts_create_contact`, `contacts_update_contact`, `contacts_delete_contact`
- aggregated Calendar and Messages permission diagnostics from the underlying standalone servers
- `apple_health`, `apple_permission_guide`, and `apple_recheck_permissions` for launch and recovery

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

## Apple Native Patterns

- Resolve a person through Contacts first, then let the assistant choose Messages or Mail from the saved defaults.
- For specific people, persist a contact-level preferred channel or address with `apple_update_contact_preferences`.
- Preview risky communication or archive actions before execution when the client wants a confirm step.
- Use Mail thread helpers when the user is talking about a conversation instead of a single message.
- Persist defaults early, archive mailbox, default calendar, default reminders list, and default notes folder, so later actions feel native instead of repeatedly asking.
- Keep contact methods current through the unified Contacts mutation tools so communication routing stays reliable.
- Keep Apple Files roots narrow and explicit, then use Files before Mail, Messages, Notes, or Shortcuts when the user references a local document.
- Use System context before interruptive actions, especially when the frontmost app, clipboard contents, or battery state affects the next step.
- Use Maps when routing, commute time, or a destination choice affects Calendar, Reminders, Messages, or Mail.
- Use `apple_list_recent_actions` and `apple_undo_action` for reversible assistant actions like archive moves and create flows.

## macOS Permissions

- Mail needs Automation access to Mail
- Calendar needs Calendar access
- Reminders needs Reminders access
- Messages needs Automation access to Messages, plus Full Disk Access for history
- Contacts needs Contacts access
- Notes needs Automation access to Notes
- Shortcuts usually works without a separate privacy prompt
- Files access is controlled by `APPLE_FILES_MCP_ALLOWED_ROOTS`, not by a macOS privacy prompt
- System actions may trigger System Events or automation prompts depending on the host app
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
