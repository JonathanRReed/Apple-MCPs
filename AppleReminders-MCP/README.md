# Apple Reminders MCP

MCP server for Apple Reminders on macOS.

Provides access to reminder lists and tasks through EventKit. Keep Reminders as the system of record while enabling agents to read, create, update, complete, and delete reminders.

## When to use

- Task and reminder assistant workflows
- Reminders isolated from the rest of the Apple stack
- EventKit-backed reminder management

## Capabilities

- Reminder-list discovery
- Reminder listing, detail, and CRUD operations
- Complete and uncomplete tools
- Today and list resources
- Planning and inbox-triage prompts
- `reminders_health`, `reminders_permission_guide`, and `reminders_recheck_permissions` for launch checks

## Install On This Mac

<details>
<summary>Quick start</summary>

```bash
cd /path/to/Apple-MCPs/AppleReminders-MCP
./start.sh
```

On first run, `start.sh` creates `.venv`, installs `requirements.txt`, and starts the server over `stdio`.

</details>

## Install In AI Agents

<details>
<summary>Generic MCP client config</summary>

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

```bash
claude mcp add --transport stdio --scope project \
  apple-reminders \
  -- /path/to/Apple-MCPs/AppleReminders-MCP/start.sh
```

</details>

## Safety Modes

- `safe_readonly`
- `safe_manage`
- `full_access`

## macOS Permissions

- Reminders access is required

## Launch Checklist

- Start the server once with `./start.sh`
- Add `/path/to/Apple-MCPs/AppleReminders-MCP/start.sh` to your MCP client
- Reload or reconnect the client so the Reminders tool surface is loaded into context
- Call `reminders_health` first
- If Reminders access is blocked, call `reminders_permission_guide`
- After changing macOS permissions, call `reminders_recheck_permissions`

## Prompting Notes

- Reminders are organized into lists. Identify available lists on first use and set a default.
- Use Reminders for due items, tasks, and follow-ups.
- `due_date` requires a timezone offset: `yyyy-MM-ddTHH:mm:ss-HH:00`

## Related

- [Apple-Tools-MCP](../Apple-Tools-MCP/README.md)
