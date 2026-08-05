<!-- mcp-name: io.github.JonathanRReed/apple-messages-mcp -->

# Apple Messages MCP

MCP server for Apple Messages on macOS.

Provides access to message history, conversation search, and sending via Messages.app. Requires Full Disk Access for history and Automation access for sending.

## When to use

- Messages-only workflows
- Message history and sending without the all-in-one server
- Tighter app-level separation for permissions

## What It Does

- List conversations with pagination
- Search messages and view attachment metadata
- Send and reply to messages
- Tool discovery helpers `search_tools` and `get_tool_info` for context-constrained clients
- Unread and recent conversation resources
- Health checks that separate history access from automation failures
- Permission recovery: `messages_permission_guide`, `messages_recheck_permissions`

## Install On This Mac

<details>
<summary>Quick start (uvx, from PyPI)</summary>

With [uv](https://docs.astral.sh/uv/getting-started/installation/) installed:

```bash
uvx apple-messages-mcp
```

No clone, no venv management.

</details>

<details>
<summary>From a clone</summary>

```bash
git clone https://github.com/JonathanRReed/Apple-MCPs.git
cd Apple-MCPs
uv sync --all-packages
```

This builds one workspace environment with every server's entry point in `.venv/bin` (for example `.venv/bin/apple-messages-mcp`). You can also point an MCP client at `AppleMessages-MCP/start.sh`, which prefers `uv run` and falls back to a plain venv bootstrap (Python 3.11+ required).

</details>

## Install In AI Agents

<details>
<summary>Generic MCP client config</summary>

```json
{
  "mcpServers": {
    "apple-messages": {
      "command": "uvx",
      "args": ["apple-messages-mcp"],
      "env": {
        "APPLE_MESSAGES_MCP_SAFETY_MODE": "full_access"
      }
    }
  }
}
```

Running from a clone instead? Use `/path/to/Apple-MCPs/AppleMessages-MCP/start.sh` as the command with empty `args`.

</details>

<details>
<summary>Claude Code example</summary>

```bash
claude mcp add --transport stdio --scope project apple-messages -- uvx apple-messages-mcp
```

</details>

## Transport

`stdio` is the default and recommended transport. Set `APPLE_MESSAGES_MCP_TRANSPORT=streamable-http` (with optional `APPLE_MESSAGES_MCP_HOST` and `APPLE_MESSAGES_MCP_PORT`) to serve Streamable HTTP instead.

## macOS Permissions

- Automation access to Messages is required for send and reply
- Full Disk Access is required for history, search, and attachment metadata from `~/Library/Messages/chat.db`
- `messages_health` reports both permission surfaces separately, so agents can tell whether send, history, or both are blocked

## Launch Checklist

- Add `uvx apple-messages-mcp` (or a clone's `AppleMessages-MCP/start.sh`) to your MCP client
- Reload or reconnect the client so the Messages tool surface is loaded into context
- Call `messages_health` first
- If either permission surface is blocked, call `messages_permission_guide`
- After changing macOS permissions, call `messages_recheck_permissions`

## Prompting Notes

- `tools/list` returns the full Messages tool surface. Context-constrained clients can use `search_tools` first, then `get_tool_info` for the Messages tool they need.
- Resolve the recipient via Contacts before any send or reply when the user names a person.
- Confirm the intended person if Contacts returns multiple matches.
- Omit `service_name` on iMessage sends. Passing it can trigger AppleScript error `-1728`.

## Related

- [Apple-Tools-MCP](../Apple-Tools-MCP/README.md)
