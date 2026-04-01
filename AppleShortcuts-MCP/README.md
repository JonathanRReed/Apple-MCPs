# Apple Shortcuts MCP

MCP server for Apple Shortcuts on macOS.

Provides access to shortcuts for discovery, inspection, and execution. Run shortcuts with structured input and output handling.

## When to use

- Triggering existing Apple Shortcuts from agents
- Local automation without shell orchestration
- Smaller scope than the all-in-one server

## Capabilities

- Shortcut and folder listing
- Shortcut inspection
- Shortcut execution with input/output handling
- Shortcut resources and execution prompts
- `shortcuts_health`, `shortcuts_permission_guide`, and `shortcuts_refresh_state` for launch checks

## Install On This Mac

<details>
<summary>Quick start</summary>

```bash
cd /path/to/Apple-MCPs/AppleShortcuts-MCP
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
    "apple-shortcuts": {
      "command": "/path/to/Apple-MCPs/AppleShortcuts-MCP/start.sh",
      "args": [],
      "env": {
        "APPLE_SHORTCUTS_MCP_SAFETY_MODE": "full_access"
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
  apple-shortcuts \
  -- /path/to/Apple-MCPs/AppleShortcuts-MCP/start.sh
```

</details>

## macOS Requirements

- the built-in `shortcuts` CLI must be available

## Launch Checklist

- Start the server once with `./start.sh`
- Add `/path/to/Apple-MCPs/AppleShortcuts-MCP/start.sh` to your MCP client
- Reload or reconnect the client so the Shortcuts tool surface is loaded into context
- Call `shortcuts_health` first
- If the CLI is unavailable, call `shortcuts_permission_guide`
- After changing the Shortcuts catalog, call `shortcuts_refresh_state`

## Prompting Notes

- If the user asks for a shortcut vaguely, list available shortcuts first.
- Run a shortcut only after confirming which shortcut to run.

## Related

- [Apple-Tools-MCP](../Apple-Tools-MCP/README.md)
