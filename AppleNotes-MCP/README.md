# Apple Notes MCP

Apple Notes access for AI agents on macOS.

This MCP lets an agent inspect accounts and folders, list and search notes, create and update notes, move notes, delete notes, and organize note folders while keeping Notes as the system of record.

## Use This Server When

- you want a notes-only assistant
- you want stronger isolation than the all-in-one server
- you want structured note and folder operations through the native Notes app

## What This MCP Gives An Agent

- account and folder listing
- note listing and search
- note create, update, move, and delete
- folder create, rename, and delete
- recent-note resources and organization prompts
- Notes mutations that resolve folders explicitly before create, update, and move operations
- `notes_health`, `notes_permission_guide`, and `notes_recheck_permissions` for launch checks

## Install On This Mac

<details>
<summary>Quick start</summary>

```bash
cd /Users/jonathanreed/Downloads/Apple-MCPs/AppleNotes-MCP
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
      "command": "/Users/jonathanreed/Downloads/Apple-MCPs/AppleNotes-MCP/start.sh",
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
  -- /Users/jonathanreed/Downloads/Apple-MCPs/AppleNotes-MCP/start.sh
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
- Add `/Users/jonathanreed/Downloads/Apple-MCPs/AppleNotes-MCP/start.sh` to your MCP client
- Reload or reconnect the client so the Notes tool surface is loaded into context
- Call `notes_health` first
- If Notes automation is blocked, call `notes_permission_guide`
- After changing macOS permissions, call `notes_recheck_permissions`

## Prompting Notes

- Multiple accounts may each contain a `Notes` folder. Identify the available accounts and folders on first use and set a default.
- Use Notes for reference material, summaries, and saved context.
- Time-sensitive items should go to Reminders or Calendar instead.

## Related

- [Apple-Tools-MCP](../Apple-Tools-MCP/README.md)
