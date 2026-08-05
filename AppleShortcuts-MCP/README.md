<!-- mcp-name: io.github.JonathanRReed/apple-shortcuts-mcp -->

# Apple Shortcuts MCP

MCP server for Apple Shortcuts on macOS.

Provides access to shortcuts for discovery, inspection, and execution. Run shortcuts with structured input and output handling.

## When to use

- Triggering existing Apple Shortcuts from agents
- Local automation without shell orchestration
- Smaller scope than the all-in-one server

## What It Does

- List shortcuts and folders
- Inspect shortcut details
- Run shortcuts with input/output handling
- Tool discovery helpers `search_tools` and `get_tool_info` for context-constrained clients
- Shortcut resources and execution prompts
- Health and state checks: `shortcuts_health`, `shortcuts_permission_guide`, `shortcuts_refresh_state`

## Install On This Mac

<details>
<summary>Quick start (uvx, from PyPI)</summary>

With [uv](https://docs.astral.sh/uv/getting-started/installation/) installed:

```bash
uvx apple-shortcuts-mcp
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

This builds one workspace environment with every server's entry point in `.venv/bin` (for example `.venv/bin/apple-shortcuts-mcp`). You can also point an MCP client at `AppleShortcuts-MCP/start.sh`, which prefers `uv run` and falls back to a plain venv bootstrap (Python 3.11+ required).

</details>

## Install In AI Agents

<details>
<summary>Generic MCP client config</summary>

```json
{
  "mcpServers": {
    "apple-shortcuts": {
      "command": "uvx",
      "args": ["apple-shortcuts-mcp"],
      "env": {
        "APPLE_SHORTCUTS_MCP_SAFETY_MODE": "full_access"
      }
    }
  }
}
```

Running from a clone instead? Use `/path/to/Apple-MCPs/AppleShortcuts-MCP/start.sh` as the command with empty `args`.

</details>

<details>
<summary>Claude Code example</summary>

```bash
claude mcp add --transport stdio --scope project apple-shortcuts -- uvx apple-shortcuts-mcp
```

</details>

## Transport

`stdio` is the default and recommended transport. Set `APPLE_SHORTCUTS_MCP_TRANSPORT=streamable-http` (with optional `APPLE_SHORTCUTS_MCP_HOST` and `APPLE_SHORTCUTS_MCP_PORT`) to serve Streamable HTTP instead.

## macOS Requirements

- the built-in `shortcuts` CLI must be available

## Launch Checklist

- Add `uvx apple-shortcuts-mcp` (or a clone's `AppleShortcuts-MCP/start.sh`) to your MCP client
- Reload or reconnect the client so the Shortcuts tool surface is loaded into context
- Call `shortcuts_health` first
- If the CLI is unavailable, call `shortcuts_permission_guide`
- After changing the Shortcuts catalog, call `shortcuts_refresh_state`

## Prompting Notes

- `tools/list` returns the full Shortcuts tool surface. Context-constrained clients can use `search_tools` first, then `get_tool_info` for the Shortcuts tool they need.
- If the user asks for a shortcut vaguely, list available shortcuts first.
- Run a shortcut only after confirming which shortcut to run.

## Related

- [Apple-Tools-MCP](../Apple-Tools-MCP/README.md)
