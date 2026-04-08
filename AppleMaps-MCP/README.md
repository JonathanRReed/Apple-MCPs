# Apple Maps MCP

Local MCP server for Apple Maps search and routing on macOS.

## Capabilities

- search for places
- estimate route distance and travel time
- build Apple Maps links
- open directions in Apple Maps
- resource: `maps://status`
- prompt: `maps_plan_route`
- search-first discovery through `search_tools` and `get_tool_info`

## Install On This Mac

<details>
<summary>Quick start</summary>

```bash
cd /path/to/Apple-MCPs/AppleMaps-MCP
./start.sh
```

`start.sh` bootstraps and repairs `.venv` as needed, reinstalls when `requirements.txt` changes, and starts the server over `stdio`.

</details>

## Install In AI Agents

```json
{
  "mcpServers": {
    "apple-maps": {
      "command": "/path/to/Apple-MCPs/AppleMaps-MCP/start.sh",
      "args": [],
      "env": {}
    }
  }
}
```

## Prompting Notes

- `tools/list` is intentionally minimal. Use `search_tools` first, then `get_tool_info` for the deferred Maps tool you need.
- Use this server when travel, routing, or place lookup affects a Calendar, Reminders, Messages, or Mail action.
- Confirm origin, destination, and transport mode before writing a time-sensitive plan.
- If helper compilation fails, install Xcode command line tools and retry.

## Health And Recovery

- `maps_health`
- `maps_permission_guide`

## Launch Checklist

- Start the server once with `./start.sh`
- Add `/path/to/Apple-MCPs/AppleMaps-MCP/start.sh` to your MCP client
- Reload or reconnect the client so the Maps tool surface is loaded into context
- Call `maps_health` first
- If the local helper or routing surface is blocked, call `maps_permission_guide`
- `maps_search_places`
