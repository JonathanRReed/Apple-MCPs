<!-- mcp-name: io.github.JonathanRReed/apple-mcp-notes -->

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
- List note attachments
- Tool discovery helpers `search_tools` and `get_tool_info` for context-constrained clients
- Recent-note resources and organization prompts
- Health and permission checks: `notes_health`, `notes_permission_guide`, `notes_recheck_permissions`

## Install On This Mac

<details>
<summary>Quick start (uvx, from PyPI)</summary>

With [uv](https://docs.astral.sh/uv/getting-started/installation/) installed:

```bash
uvx apple-mcp-notes
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

This builds one workspace environment with every server's entry point in `.venv/bin` (for example `.venv/bin/apple-notes-mcp`). You can also point an MCP client at `AppleNotes-MCP/start.sh`, which prefers `uv run` and falls back to a plain venv bootstrap (Python 3.11+ required).

</details>

## Install In AI Agents

<details>
<summary>Generic MCP client config</summary>

```json
{
  "mcpServers": {
    "apple-notes": {
      "command": "uvx",
      "args": ["apple-mcp-notes"],
      "env": {
        "APPLE_NOTES_MCP_SAFETY_MODE": "full_access"
      }
    }
  }
}
```

Running from a clone instead? Use `/path/to/Apple-MCPs/AppleNotes-MCP/start.sh` as the command with empty `args`.

</details>

<details>
<summary>Claude Code example</summary>

```bash
claude mcp add --transport stdio --scope project apple-notes -- uvx apple-mcp-notes
```

</details>

## Safety Modes

- `safe_readonly`
- `safe_manage`
- `full_access`

## Transport

`stdio` is the default and recommended transport. Set `APPLE_NOTES_MCP_TRANSPORT=streamable-http` (with optional `APPLE_NOTES_MCP_HOST` and `APPLE_NOTES_MCP_PORT`) to serve Streamable HTTP instead.

## macOS Permissions

- Automation access to Notes is required

## Launch Checklist

- Add `uvx apple-mcp-notes` (or a clone's `AppleNotes-MCP/start.sh`) to your MCP client
- Reload or reconnect the client so the Notes tool surface is loaded into context
- Call `notes_health` first
- If Notes automation is blocked, call `notes_permission_guide`
- After changing macOS permissions, call `notes_recheck_permissions`

## Prompting Notes

- `tools/list` returns the full Notes tool surface. Context-constrained clients can use `search_tools` first, then `get_tool_info` for the Notes tool they need.
- Multiple accounts may each contain a Notes folder. Identify available accounts and folders on first use and set a default.
- Use Notes for reference material and saved context.
- Time-sensitive items should go to Reminders or Calendar instead.

## Related

- [Apple-Tools-MCP](../Apple-Tools-MCP/README.md)
