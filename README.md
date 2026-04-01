# Apple-MCPs

Apple-native MCP servers for macOS.

This repository gives AI agents direct, local access to core Apple apps and adjacent macOS context through the Model Context Protocol (MCP). Agents can use structured tools, read resources, and follow built-in prompts instead of attempting to control your Mac blindly.

## What MCP Means Here

Each MCP server in this repo runs locally on your Mac and exposes app-specific capabilities over `stdio`.

- tools let an agent take actions, like creating a reminder or sending a message
- resources let an agent read compact snapshots, like recent notes or today’s reminders
- prompts give agents better app-specific workflows, like planning the day or triaging communication

Because these servers run on your Mac, the Apple apps stay the system of record.

## Servers

- [Apple-Tools-MCP](./Apple-Tools-MCP/README.md), recommended. One unified server for Mail, Calendar, Reminders, Messages, Contacts, Notes, Shortcuts, Files, System, and Maps.
- [Apple Files MCP](./AppleFiles-MCP/README.md), for safe file and folder workflows inside allowed roots.
- [Apple System MCP](./AppleSystem-MCP/README.md), for frontmost app, battery, clipboard, notifications, and app-launch context.
- [Apple Maps MCP](./AppleMaps-MCP/README.md), for place search, travel estimates, and Apple Maps links.
- [Apple Mail MCP](./AppleMail-MCP/README.md), for Mail-only workflows.
- [Apple Calendar](./Apple-Calendar-MCP/README.md), for Calendar-only workflows.
- [Apple Reminders MCP](./AppleReminders-MCP/README.md), for task and reminder workflows.
- [Apple Messages MCP](./AppleMessages-MCP/README.md), for iMessage and Messages workflows.
- [Apple Contacts MCP](./AppleContacts-MCP/README.md), for contacts and recipient-resolution workflows.
- [Apple Notes MCP](./AppleNotes-MCP/README.md), for notes and knowledge workflows.
- [Apple Shortcuts MCP](./AppleShortcuts-MCP/README.md), for running Apple Shortcuts from agents.

## Which One To Use

- Use `Apple-Tools-MCP` for a single entrypoint across all Apple apps
- Use `Apple-Tools-MCP` if you want assistant behavior, persisted defaults, contact-specific routing, thread-aware Mail workflows, preview and undo helpers, file-aware attachment prep, system context, and travel-aware workflows on top of the raw app tools
- Use `Apple-Tools-MCP` if you want task-capable long-running briefings, tool-only prompt fallback, and the broadest MCP protocol surface in one server
- Use `Apple Files MCP`, `Apple System MCP`, or `Apple Maps MCP` when you want a narrower tool surface for local files, desktop context, or travel routing without the unified assistant layer
- Use standalone servers for tighter app boundaries, simpler permissions, or separate agent configurations

## Agent Routing

- All Apple tool schemas are deferred. Batch `tool_search` calls on first use.
- Route person-based communication through Contacts first.
- Use Contacts to verify or update phone numbers and email addresses before a send path fails.
- Use Mail thread helpers when the user refers to a conversation or latest reply.
- Use Apple-Tools preview and recent-action helpers when the client needs a confirm step or an audit trail.
- Use Reminders for due items, Notes for reference material, and Calendar for scheduled time.
- See the standalone READMEs for app-specific prompting rules and gotchas.

## Install On This Mac

<details>
<summary>Recommended, install the all-in-one server</summary>

```bash
cd /path/to/Apple-MCPs/Apple-Tools-MCP
./start.sh
```

`start.sh` creates a local virtual environment on first run, installs the Python dependencies from `requirements.txt`, and starts the MCP server over `stdio`.

</details>

<details>
<summary>Install one standalone server instead</summary>

Example:

```bash
cd /path/to/Apple-MCPs/AppleMessages-MCP
./start.sh
```

Every server folder follows the same pattern:

- `manifest.json`
- `start.sh`
- `server.py`
- `README.md`
- `src/`
- `tests/`

</details>

## Install In AI Agents

<details>
<summary>Generic MCP client, stdio config</summary>

Most MCP clients that support local `stdio` servers can point directly at a server `start.sh`.

Example for the all-in-one server:

```json
{
  "mcpServers": {
    "apple-tools": {
      "command": "/path/to/Apple-MCPs/Apple-Tools-MCP/start.sh",
      "args": [],
      "env": {}
    }
  }
}
```

Example for a standalone server:

```json
{
  "mcpServers": {
    "apple-reminders": {
      "command": "/path/to/Apple-MCPs/AppleReminders-MCP/start.sh",
      "args": [],
      "env": {
        "APPLE_REMINDERS_MCP_SAFETY_MODE": "safe_manage"
      }
    }
  }
}
```

</details>

<details>
<summary>Claude Code example</summary>

Add the all-in-one server:

```bash
claude mcp add --transport stdio --scope project \
  apple-tools \
  -- /path/to/Apple-MCPs/Apple-Tools-MCP/start.sh
```

Add a standalone server:

```bash
claude mcp add --transport stdio --scope project \
  apple-notes \
  -- /path/to/Apple-MCPs/AppleNotes-MCP/start.sh
```

</details>

## Launch Checklist

- Start the server you want with its local `./start.sh`
- Add that `start.sh` path to your MCP client
- Reload or reconnect the client so the server is loaded into context
- Call the server's health tool before doing real work
- If permissions are blocked, call the server's permission guide tool
- After changing permissions, call the server's recheck tool, or `shortcuts_refresh_state` for Apple Shortcuts

## Protocol Verification

Use `stdio` for normal local agent setups. Apple-Tools-MCP also supports `streamable-http` for protocol validation and hosted clients.

Run the full official active server conformance suite against Apple-Tools-MCP:

```bash
cd /path/to/Apple-MCPs/Apple-Tools-MCP
APPLE_AGENT_MCP_TRANSPORT=streamable-http \
APPLE_AGENT_MCP_PORT=8765 \
APPLE_AGENT_MCP_CONFORMANCE_MODE=1 \
./start.sh
```

In another shell:

```bash
npx -y @modelcontextprotocol/conformance server \
  --url http://127.0.0.1:8765/mcp \
  --suite active
```

Run lightweight Inspector smoke checks across all published servers:

```bash
cd /path/to/Apple-MCPs
bash scripts/inspector_smoke.sh
```

The repository also includes GitHub Actions for both checks in [protocol-ci.yml](./.github/workflows/protocol-ci.yml).

## Health And Recovery Tools

| Server | Health tool | Permission or recovery tools |
| --- | --- | --- |
| Apple-Tools-MCP | `apple_health` | `apple_permission_guide`, `apple_recheck_permissions` |
| Apple Mail MCP | `mail_health` | `mail_permission_guide`, `mail_recheck_permissions` |
| Apple Calendar | `calendar_health` | `calendar_permission_guide`, `calendar_recheck_permissions` |
| Apple Reminders MCP | `reminders_health` | `reminders_permission_guide`, `reminders_recheck_permissions` |
| Apple Messages MCP | `messages_health` | `messages_permission_guide`, `messages_recheck_permissions` |
| Apple Contacts MCP | `contacts_health` | `contacts_permission_guide`, `contacts_recheck_permissions` |
| Apple Notes MCP | `notes_health` | `notes_permission_guide`, `notes_recheck_permissions` |
| Apple Shortcuts MCP | `shortcuts_health` | `shortcuts_permission_guide`, `shortcuts_refresh_state` |
| Apple Files MCP | `files_health` | `files_permission_guide` |
| Apple System MCP | `system_health` | `system_permission_guide` |
| Apple Maps MCP | `maps_health` | `maps_permission_guide` |

## macOS Permissions

Different Apple apps require different permissions:

| Server | What macOS may ask for |
| --- | --- |
| Apple Mail | Automation access to Mail |
| Apple Calendar | Calendar access |
| Apple Reminders | Reminders access |
| Apple Messages | Automation access to Messages, plus Full Disk Access for history |
| Apple Contacts | Contacts access |
| Apple Notes | Automation access to Notes |
| Apple Shortcuts | Usually no separate privacy prompt |
| Apple Files | No privacy prompt, access is limited by the configured allowed roots |
| Apple System | Some actions may trigger System Events or automation prompts |
| Apple Maps | No privacy prompt, but local Swift helper compilation needs Xcode command line tools |

## Repo Layout

- `Apple-Tools-MCP/`, unified server
- `AppleFiles-MCP/`, Files
- `AppleSystem-MCP/`, System
- `AppleMaps-MCP/`, Maps
- `AppleContacts-MCP/`, Contacts
- `AppleMail-MCP/`, Mail
- `Apple-Calendar-MCP/`, Calendar
- `AppleReminders-MCP/`, Reminders
- `AppleMessages-MCP/`, Messages
- `AppleNotes-MCP/`, Notes
- `AppleShortcuts-MCP/`, Shortcuts
- `SharedAppleBridge/`, shared native bridge code used by EventKit-backed servers
- `.build/`, local helper build output

## Notes

- This suite is for macOS.
- Apple Messages history access still needs Full Disk Access.
- The unified server folder is `Apple-Tools-MCP`.
- The calendar server folder is `Apple-Calendar-MCP`.
- Apple Files access is limited to the roots in `APPLE_FILES_MCP_ALLOWED_ROOTS`.
- Apple System write actions can be scoped down with `APPLE_SYSTEM_MCP_SAFETY_MODE`.
- Apple Maps depends on a local Swift helper and Xcode command line tools for search and directions.
- Apple-Tools-MCP can persist assistant defaults in `~/.apple-tools-mcp/preferences.json`, or the path from `APPLE_AGENT_MCP_STATE_FILE`.
- Apple-Tools-MCP also stores recent assistant actions in `~/.apple-tools-mcp/actions.json` for audit and undo workflows.
- Apple-Tools-MCP now aggregates Files, System, and Maps alongside the app-specific Apple servers.
- `APPLE_AGENT_MCP_CONFORMANCE_MODE=1` is for protocol validation only. It adds the official MCP conformance fixtures on Apple-Tools-MCP and switches HTTP mode to full streaming behavior.
- Apple-Tools-MCP now includes task-capable briefing tools, `apple_generate_daily_briefing`, `apple_generate_weekly_briefing`, and `apple_triage_communications_task`.
- Apple-Tools-MCP also includes prompt fallback tools, `apple_list_prompts` and `apple_get_prompt`, for tool-only MCP clients.
- The standalone servers now expose prompt fallback tools and explicit resource subscribe or unsubscribe handlers, so prompt-heavy workflows degrade more cleanly in thinner MCP clients.
- Apple Mail now includes thread helpers, `mail_get_thread`, `mail_reply_latest_in_thread`, and `mail_archive_thread`.
- Apple Contacts can now create, update, and delete contacts with labeled phone numbers and email addresses.
- Mail search requires a query string. Use a sender, a subject fragment, or `*` as a wildcard.
- Reminders `due_date` requires a timezone offset like `yyyy-MM-ddTHH:mm:ss-HH:00`.
- `service_name` should be omitted on iMessage sends.
