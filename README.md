# Apple-MCPs

Apple-native MCP servers for macOS.

This repository provides direct, local access to core Apple apps through the Model Context Protocol (MCP). Your AI assistant can use structured tools to work with your data—create reminders, send messages, check calendars—while everything stays in the native apps you already use.

MCP provides three primitives for working with Apple apps:

- **Tools** — actions like creating a reminder or sending a message
- **Resources** — read-only snapshots like recent notes or today's reminders
- **Prompts** — reusable workflows for common tasks like planning your day

Everything happens on your Mac. Your data stays in Apple's apps where it belongs.

## Project Docs

- [CHANGELOG.md](./CHANGELOG.md)
- [CONTRIBUTING.md](./CONTRIBUTING.md)
- [SECURITY.md](./SECURITY.md)

## Launch Docs

- [Golden Workflows](./docs/launch/golden-workflows.md)
- [Failure Modes](./docs/launch/failure-modes.md)
- [Compatibility and Version Pinning](./docs/launch/compatibility.md)
- [Demo Script](./docs/launch/demo-script.md)
- [Checklist Template Prompt](./docs/launch/prompts/checklist-template.md)
- [Per-Server E2E Checklist](./docs/launch/prompts/per-server-e2e-checklist.md)

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

**Apple-Tools-MCP** (recommended) — One server that covers everything: Mail, Calendar, Reminders, Messages, Contacts, Notes, Shortcuts, Files, System, and Maps. Includes extras like saved defaults, per-contact routing preferences, thread-aware Mail helpers, and undo support.

**Standalone servers** — Pick one if you want tighter boundaries or simpler permissions:
- [Apple Files MCP](./AppleFiles-MCP/README.md), [Apple System MCP](./AppleSystem-MCP/README.md), [Apple Maps MCP](./AppleMaps-MCP/README.md) for focused workflows
- [Apple Mail MCP](./AppleMail-MCP/README.md), [Apple Calendar](./Apple-Calendar-MCP/README.md), [Apple Reminders MCP](./AppleReminders-MCP/README.md), [Apple Messages MCP](./AppleMessages-MCP/README.md), [Apple Contacts MCP](./AppleContacts-MCP/README.md), [Apple Notes MCP](./AppleNotes-MCP/README.md), [Apple Shortcuts MCP](./AppleShortcuts-MCP/README.md) for single-app access

## Agent Routing

Some tips for working with these servers:

- All Apple tools are deferred. The first call needs `tool_search` to load schemas.
- Always run Contacts first when messaging a person, then choose Messages or Mail.
- Use Mail thread helpers when the user mentions a conversation.
- Reminders are for due items, Notes for reference material, Calendar for scheduled time.
- See the standalone READMEs for app-specific details.

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
<summary>Install every package into one shared environment</summary>

```bash
cd /path/to/Apple-MCPs
bash scripts/install_all.sh
```

This creates a shared virtual environment and installs every standalone package plus `Apple-Tools-MCP` into it. Use this when you want one environment that can run any server without relying on sibling source-path imports.

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

- Start the server: `./start.sh`
- Add the `start.sh` path to your MCP client
- Reconnect the client so the server loads
- Call the health tool to verify it's working
- If permissions fail, call the permission guide tool
- After fixing permissions, call the recheck tool (or `shortcuts_refresh_state` for Shortcuts)

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
