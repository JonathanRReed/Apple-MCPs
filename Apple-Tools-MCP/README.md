# Apple-Tools-MCP

One Apple-native MCP server for macOS.

This server gives an AI agent one entrypoint for Apple Mail, Calendar, Reminders, Messages, Contacts, Notes, and Shortcuts. It reuses the standalone servers in this repo and exposes one unified MCP surface on top of them.

## What This MCP Gives An Agent

- one place to read Apple context across apps
- one place to act across apps
- cross-app prompts for day planning, communications triage, and meeting prep
- one install target instead of seven separate agent configs

## Use This Server When

- you want one personal-assistant MCP for the Apple apps in this repo
- you want cross-app workflows, like using Calendar and Reminders together
- you do not want to wire each standalone MCP separately

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

## Related Servers

- [Apple Mail MCP](../AppleMail-MCP/README.md)
- [Apple Calendar](../Apple-Calendar-MCP/README.md)
- [Apple Reminders MCP](../AppleReminders-MCP/README.md)
- [Apple Messages MCP](../AppleMessages-MCP/README.md)
- [Apple Contacts MCP](../AppleContacts-MCP/README.md)
- [Apple Notes MCP](../AppleNotes-MCP/README.md)
- [Apple Shortcuts MCP](../AppleShortcuts-MCP/README.md)
