# Apple Maps MCP

Local MCP server for Apple Maps search and routing on macOS.

## Capabilities

- search for places
- estimate route distance and travel time
- build Apple Maps links
- open directions in Apple Maps
- resource: `maps://status`
- prompt: `maps_plan_route`

## Install On This Mac

```bash
cd /path/to/Apple-MCPs/AppleMaps-MCP
./start.sh
```

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

- Use this server when travel, routing, or place lookup affects a Calendar, Reminders, Messages, or Mail action.
- Confirm origin, destination, and transport mode before writing a time-sensitive plan.
- If helper compilation fails, install Xcode command line tools and retry.

## Health And Recovery

- `maps_health`
- `maps_permission_guide`
- `maps_search_places`
