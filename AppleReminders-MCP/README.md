<!-- mcp-name: io.github.jonathanrreed/apple-mcp-reminders -->

# Apple Reminders MCP

MCP server for Apple Reminders on macOS.

Provides access to reminder lists and tasks through EventKit. Keep Reminders as the system of record while enabling agents to read, create, update, complete, and delete reminders.

## When to use

- Task and reminder workflows
- Reminders isolated from the rest of the Apple stack
- EventKit-backed reminder management

## What It Does

- Discover, create, and delete reminder lists
- List, create, update, and delete reminders
- Complete and uncomplete tasks
- Tool discovery helpers `search_tools` and `get_tool_info` for context-constrained clients
- Today and list resources
- Planning and inbox-triage prompts
- Health and permission checks: `reminders_health`, `reminders_permission_guide`, `reminders_recheck_permissions`

## Install On This Mac

<details>
<summary>Quick start (uvx, from PyPI)</summary>

With [uv](https://docs.astral.sh/uv/getting-started/installation/) installed:

```bash
uvx apple-mcp-reminders
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

This builds one workspace environment with every server's entry point in `.venv/bin` (for example `.venv/bin/apple-reminders-mcp`). You can also point an MCP client at `AppleReminders-MCP/start.sh`, which prefers `uv run` and falls back to a plain venv bootstrap (Python 3.11+ required).

</details>

## Install In AI Agents

<details>
<summary>Generic MCP client config</summary>

```json
{
  "mcpServers": {
    "apple-reminders": {
      "command": "uvx",
      "args": ["apple-mcp-reminders"],
      "env": {
        "APPLE_REMINDERS_MCP_SAFETY_MODE": "safe_manage"
      }
    }
  }
}
```

Running from a clone instead? Use `/path/to/Apple-MCPs/AppleReminders-MCP/start.sh` as the command with empty `args`.

</details>

<details>
<summary>Claude Code example</summary>

```bash
claude mcp add --transport stdio --scope project apple-reminders -- uvx apple-mcp-reminders
```

</details>

## Safety Modes

- `safe_readonly`
- `safe_manage`
- `full_access`

## Transport

`stdio` is the default and recommended transport. Set `APPLE_REMINDERS_MCP_TRANSPORT=streamable-http` (with optional `APPLE_REMINDERS_MCP_HOST` and `APPLE_REMINDERS_MCP_PORT`) to serve Streamable HTTP instead.

## macOS Permissions

- Reminders access is required

## Launch Checklist

- Add `uvx apple-mcp-reminders` (or a clone's `AppleReminders-MCP/start.sh`) to your MCP client
- Reload or reconnect the client so the Reminders tool surface is loaded into context
- Call `reminders_health` first
- If Reminders access is blocked, call `reminders_permission_guide`
- After changing macOS permissions, call `reminders_recheck_permissions`

## Prompting Notes

- `tools/list` returns the full Reminders tool surface. Context-constrained clients can use `search_tools` first, then `get_tool_info` for the Reminders tool they need.
- Reminders are organized into lists. Identify available lists on first use and set a default.
- Use Reminders for due items, tasks, and follow-ups.
- `due_date` requires a timezone offset: `yyyy-MM-ddTHH:mm:ss-HH:00`

## Related

- [Apple-Tools-MCP](../Apple-Tools-MCP/README.md)
