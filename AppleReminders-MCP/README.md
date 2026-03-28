# Apple Reminders MCP

Apple Reminders access for AI agents on macOS.

This MCP lets an agent list reminder lists, inspect reminders, create reminders, edit reminder details, complete tasks, uncomplete tasks, and delete reminders while keeping Reminders as the system of record.

## Use This Server When

- you want a task and reminders assistant
- you want reminders isolated from the rest of the Apple stack
- you want EventKit-backed reminder management

## What This MCP Gives An Agent

- reminder-list discovery
- reminder listing and detail
- create and update tools
- complete and uncomplete tools
- today and list resources
- planning and inbox-triage prompts

## Install On This Mac

<details>
<summary>Quick start</summary>

```bash
cd /Users/jonathanreed/Downloads/Apple-MCPs/AppleReminders-MCP
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

```bash
claude mcp add --transport stdio --scope project \
  apple-reminders \
  -- /Users/jonathanreed/Downloads/Apple-MCPs/AppleReminders-MCP/start.sh
```

</details>

## Safety Modes

- `safe_readonly`
- `safe_manage`
- `full_access`

## macOS Permissions

- Reminders access is required

## Related

- [Apple AIO MCP](../Apple-AIO-MCP/README.md)
