# Apple-MCPs

Apple-native MCP servers for macOS.

This repo gives AI agents direct, local access to core Apple apps through the Model Context Protocol, or MCP. In practice, that means an agent can call structured tools, read lightweight resources, and use built-in prompts instead of trying to control your Mac blindly.

## What MCP Means Here

Each MCP server in this repo runs locally on your Mac and exposes app-specific capabilities over `stdio`.

- tools let an agent take actions, like creating a reminder or sending a message
- resources let an agent read compact snapshots, like recent notes or today’s reminders
- prompts give agents better app-specific workflows, like planning the day or triaging communication

Because these servers run on your Mac, the Apple apps stay the system of record.

## Servers

- [Apple-Tools-MCP](./Apple-Tools-MCP/README.md), recommended. One unified server for Mail, Calendar, Reminders, Messages, Contacts, Notes, and Shortcuts.
- [Apple Mail MCP](./AppleMail-MCP/README.md), for Mail-only workflows.
- [Apple Calendar](./Apple-Calendar-MCP/README.md), for Calendar-only workflows.
- [Apple Reminders MCP](./AppleReminders-MCP/README.md), for task and reminder workflows.
- [Apple Messages MCP](./AppleMessages-MCP/README.md), for iMessage and Messages workflows.
- [Apple Contacts MCP](./AppleContacts-MCP/README.md), for contacts and recipient-resolution workflows.
- [Apple Notes MCP](./AppleNotes-MCP/README.md), for notes and knowledge workflows.
- [Apple Shortcuts MCP](./AppleShortcuts-MCP/README.md), for running Apple Shortcuts from agents.

## Which One To Use

- Use `Apple-Tools-MCP` if you want one assistant entrypoint across the Apple apps in this repo.
- Use the standalone servers if you want tighter app boundaries, simpler permissions, or separate agent configs.

## Agent Routing

- All Apple tool schemas are deferred. Batch `tool_search` calls on first use.
- Route person-based communication through Contacts first.
- Use Reminders for due items, Notes for reference material, and Calendar for scheduled time.
- See the standalone READMEs for app-specific prompting rules and gotchas.

## Install On This Mac

<details>
<summary>Recommended, install the all-in-one server</summary>

```bash
cd /Users/jonathanreed/Downloads/Apple-MCPs/Apple-Tools-MCP
./start.sh
```

`start.sh` creates a local virtual environment on first run, installs the Python dependencies from `requirements.txt`, and starts the MCP server over `stdio`.

</details>

<details>
<summary>Install one standalone server instead</summary>

Example:

```bash
cd /Users/jonathanreed/Downloads/Apple-MCPs/AppleMessages-MCP
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
      "command": "/Users/jonathanreed/Downloads/Apple-MCPs/Apple-Tools-MCP/start.sh",
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
      "command": "/Users/jonathanreed/Downloads/Apple-MCPs/AppleReminders-MCP/start.sh",
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
  -- /Users/jonathanreed/Downloads/Apple-MCPs/Apple-Tools-MCP/start.sh
```

Add a standalone server:

```bash
claude mcp add --transport stdio --scope project \
  apple-notes \
  -- /Users/jonathanreed/Downloads/Apple-MCPs/AppleNotes-MCP/start.sh
```

</details>

## Launch Checklist

- Start the server you want with its local `./start.sh`
- Add that `start.sh` path to your MCP client
- Reload or reconnect the client so the server is loaded into context
- Call the server's health tool before doing real work
- If permissions are blocked, call the server's permission guide tool
- After changing permissions, call the server's recheck tool, or `shortcuts_refresh_state` for Apple Shortcuts

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

## Repo Layout

- `Apple-Tools-MCP/`, unified server
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
- Mail search requires a query string. Use a sender, a subject fragment, or `*` as a wildcard.
- Reminders `due_date` requires a timezone offset like `yyyy-MM-ddTHH:mm:ss-HH:00`.
- `service_name` should be omitted on iMessage sends.
