# Apple Messages MCP

Apple Messages access for AI agents on macOS.

This MCP lets an agent read Messages history, inspect threads, search messages, list attachments, and send or reply through Messages.app.

## Use This Server When

- you want an agent focused on Messages only
- you want message history and sending without the all-in-one server
- you want tighter app-level separation for permissions

## What This MCP Gives An Agent

- conversation listing
- conversation detail and pagination
- message search
- attachment metadata
- send and reply tools
- unread and recent conversation resources
- health output that separates history access failures from automation failures
- `messages_permission_guide` and `messages_recheck_permissions` for permission recovery

## Install On This Mac

<details>
<summary>Quick start</summary>

```bash
cd /Users/jonathanreed/Downloads/Apple-MCPs/AppleMessages-MCP
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
    "apple-messages": {
      "command": "/Users/jonathanreed/Downloads/Apple-MCPs/AppleMessages-MCP/start.sh",
      "args": [],
      "env": {
        "APPLE_MESSAGES_MCP_SAFETY_MODE": "full_access"
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
  apple-messages \
  -- /Users/jonathanreed/Downloads/Apple-MCPs/AppleMessages-MCP/start.sh
```

</details>

## macOS Permissions

- Automation access to Messages is required for send and reply
- Full Disk Access is required for history, search, and attachment metadata from `~/Library/Messages/chat.db`
- `messages_health` reports both permission surfaces separately, so agents can tell whether send, history, or both are blocked

## Launch Checklist

- Start the server once with `./start.sh`
- Add `/Users/jonathanreed/Downloads/Apple-MCPs/AppleMessages-MCP/start.sh` to your MCP client
- Reload or reconnect the client so the Messages tool surface is loaded into context
- Call `messages_health` first
- If either permission surface is blocked, call `messages_permission_guide`
- After changing macOS permissions, call `messages_recheck_permissions`

## Related

- [Apple-Tools-MCP](../Apple-AIO-MCP/README.md)
