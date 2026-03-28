# Apple Shortcuts MCP

Apple Shortcuts access for AI agents on macOS.

This MCP lets an agent discover shortcuts, inspect shortcut metadata, browse shortcut folders, and run shortcuts with structured input and output handling.

## Use This Server When

- you want an agent to trigger existing Apple Shortcuts
- you want a local automation bridge without shell orchestration
- you want a smaller scope than the all-in-one server

## What This MCP Gives An Agent

- shortcut listing
- folder listing
- shortcut inspection
- shortcut execution
- shortcut resources and execution prompts

## Install On This Mac

<details>
<summary>Quick start</summary>

```bash
cd /Users/jonathanreed/Downloads/Apple-MCPs/AppleShortcuts-MCP
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
      "command": "/Users/jonathanreed/Downloads/Apple-MCPs/AppleShortcuts-MCP/start.sh",
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
  -- /Users/jonathanreed/Downloads/Apple-MCPs/AppleShortcuts-MCP/start.sh
```

</details>

## macOS Requirements

- the built-in `shortcuts` CLI must be available

## Related

- [Apple AIO MCP](../Apple-AIO-MCP/README.md)
