# Apple-Tools-MCP

Unified MCP server for Apple apps on macOS.

One entrypoint for Mail, Calendar, Reminders, Messages, Contacts, Notes, and Shortcuts. This server wraps the standalone servers in this repository and exposes a unified MCP interface.

## Capabilities

- Cross-app context reading
- Unified action interface across all apps
- Cross-app prompts for day planning, communications triage, and meeting prep
- Single install target instead of seven separate configurations

## When to use

- Personal assistant workflows across multiple Apple apps
- Cross-app operations (e.g., Calendar and Reminders together)
- Simpler setup without wiring each standalone MCP separately

## Install On This Mac

<details>
<summary>Quick start</summary>

```bash
cd /Users/jonathanreed/Downloads/Apple-MCPs/Apple-Tools-MCP
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
      "command": "/Users/jonathanreed/Downloads/Apple-MCPs/Apple-Tools-MCP/start.sh",
      "args": [],
      "env": {
        "APPLE_MAIL_MCP_SAFETY_PROFILE": "full_access",
        "APPLE_CALENDAR_MCP_SAFETY_MODE": "safe_manage",
        "APPLE_REMINDERS_MCP_SAFETY_MODE": "safe_manage",
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
  -- /Users/jonathanreed/Downloads/Apple-MCPs/Apple-Tools-MCP/start.sh
```

</details>

## What It Exposes

- aggregated health and overview tools
- cross-app prompts
- the delegated Mail, Calendar, Reminders, Messages, Contacts, Notes, and Shortcuts tools
- Apple-wide suggestion and permission-guide tools
- aggregated Calendar and Messages permission diagnostics from the underlying standalone servers
- `apple_health`, `apple_permission_guide`, and `apple_recheck_permissions` for launch and recovery

## macOS Permissions

- Mail needs Automation access to Mail
- Calendar needs Calendar access
- Reminders needs Reminders access
- Messages needs Automation access to Messages, plus Full Disk Access for history
- Contacts needs Contacts access
- Notes needs Automation access to Notes
- Shortcuts usually works without a separate privacy prompt

## Launch Checklist

- Start the server once with `./start.sh`
- Add `/Users/jonathanreed/Downloads/Apple-MCPs/Apple-Tools-MCP/start.sh` to your MCP client
- Reload or reconnect the client so the Apple-Tools-MCP tool surface is loaded into context
- Call `apple_health` first to verify every domain
- If a domain is blocked, call `apple_permission_guide`
- After changing macOS permissions, call `apple_recheck_permissions`

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
</known_gotchas>
</apple_tools>
```

## Related Servers

- [Apple Mail MCP](../AppleMail-MCP/README.md)
- [Apple Calendar](../Apple-Calendar-MCP/README.md)
- [Apple Reminders MCP](../AppleReminders-MCP/README.md)
- [Apple Messages MCP](../AppleMessages-MCP/README.md)
- [Apple Contacts MCP](../AppleContacts-MCP/README.md)
- [Apple Notes MCP](../AppleNotes-MCP/README.md)
- [Apple Shortcuts MCP](../AppleShortcuts-MCP/README.md)
