<!-- mcp-name: io.github.jonathanrreed/apple-maps-mcp -->

# Apple Maps MCP

Local MCP server for Apple Maps search and routing on macOS.

## Capabilities

- search for places
- estimate route distance and travel time
- build Apple Maps links
- open directions in Apple Maps
- resource: `maps://status`
- prompt: `maps_plan_route`
- tool discovery helpers `search_tools` and `get_tool_info` for context-constrained clients

## Install On This Mac

<details>
<summary>Quick start (uvx, from PyPI)</summary>

With [uv](https://docs.astral.sh/uv/getting-started/installation/) installed:

```bash
uvx apple-maps-mcp
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

This builds one workspace environment with every server's entry point in `.venv/bin` (for example `.venv/bin/apple-maps-mcp`). You can also point an MCP client at `AppleMaps-MCP/start.sh`, which prefers `uv run` and falls back to a plain venv bootstrap (Python 3.11+ required).

</details>

## Install In AI Agents

```json
{
  "mcpServers": {
    "apple-maps": {
      "command": "uvx",
      "args": ["apple-maps-mcp"],
      "env": {}
    }
  }
}
```

Running from a clone instead? Use `/path/to/Apple-MCPs/AppleMaps-MCP/start.sh` as the command with empty `args`.

Claude Code:

```bash
claude mcp add --transport stdio --scope project apple-maps -- uvx apple-maps-mcp
```

## Transport

`stdio` is the default and recommended transport. Set `APPLE_MAPS_MCP_TRANSPORT=streamable-http` (with optional `APPLE_MAPS_MCP_HOST` and `APPLE_MAPS_MCP_PORT`) to serve Streamable HTTP instead.

## Prompting Notes

- `tools/list` returns the full Maps tool surface. Context-constrained clients can use `search_tools` first, then `get_tool_info` for the Maps tool they need.
- Use this server when travel, routing, or place lookup affects a Calendar, Reminders, Messages, or Mail action.
- Confirm origin, destination, and transport mode before writing a time-sensitive plan.
- If helper compilation fails, install Xcode command line tools and retry.

## Health And Recovery

- `maps_health`
- `maps_permission_guide`

## Launch Checklist

- Add `uvx apple-maps-mcp` (or a clone's `AppleMaps-MCP/start.sh`) to your MCP client
- Reload or reconnect the client so the Maps tool surface is loaded into context
- Call `maps_health` first
- If the local helper or routing surface is blocked, call `maps_permission_guide`
- Run `maps_search_places` once to confirm the local Swift helper compiles
