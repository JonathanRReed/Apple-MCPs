# Apple Notes MCP

MCP server for Apple Notes on macOS.

Provides access to notes and folders for creation, organization, and management. Keep Notes as the system of record while enabling agents to read, create, update, move, and delete notes.

## When to use

- Notes-only workflows
- Stronger isolation than the all-in-one server
- Structured note and folder operations through the native Notes app

## What It Does

- List accounts and folders
- List, search, and manage notes (CRUD)
- Create, rename, and delete folders
- Recent-note resources and organization prompts
- Health and permission checks: `notes_health`, `notes_permission_guide`, `notes_recheck_permissions`

## Install On This Mac

<details>
<summary>Quick start</summary>

```bash
cd /path/to/Apple-MCPs/AppleNotes-MCP
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
    "apple-notes": {
      "command": "/path/to/Apple-MCPs/AppleNotes-MCP/start.sh",
      "args": [],
      "env": {
        "APPLE_NOTES_MCP_SAFETY_MODE": "full_access"
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
  apple-notes \
  -- /path/to/Apple-MCPs/AppleNotes-MCP/start.sh
```

</details>

## Safety Modes

- `safe_readonly`
- `safe_manage`
- `full_access`

## macOS Permissions

- Automation access to Notes is required

## Launch Checklist

- Start the server once with `./start.sh`
- Add `/path/to/Apple-MCPs/AppleNotes-MCP/start.sh` to your MCP client
- Reload or reconnect the client so the Notes tool surface is loaded into context
- Call `notes_health` first
- If Notes automation is blocked, call `notes_permission_guide`
- After changing macOS permissions, call `notes_recheck_permissions`

## Prompting Notes

- Multiple accounts may each contain a Notes folder. Identify available accounts and folders on first use and set a default.
- Use Notes for reference material and saved context.
- Time-sensitive items should go to Reminders or Calendar instead.

## Related

- [Apple-Tools-MCP](../Apple-Tools-MCP/README.md)
