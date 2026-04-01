# Apple Messages MCP

MCP server for Apple Messages on macOS.

Provides access to message history, conversation search, and sending via Messages.app. Requires Full Disk Access for history and Automation access for sending.

## When to use

- Messages-only assistant workflows
- Message history and sending without the all-in-one server
- Tighter app-level separation for permissions

## Capabilities

- Conversation listing and detail with pagination
- Message search and attachment metadata
- Send and reply tools
- Unread and recent conversation resources
- Health checks that separate history access from automation failures
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

## Prompting Notes

- Resolve the recipient via Contacts before any send or reply when the user names a person.
- Confirm the intended person if Contacts returns multiple matches.
- Omit `service_name` on iMessage sends. Passing it can trigger AppleScript error `-1728`.

## Related

- [Apple-Tools-MCP](../Apple-Tools-MCP/README.md)
