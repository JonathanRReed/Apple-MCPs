# Apple System MCP

Local MCP server for lightweight macOS system context.

## Capabilities

- battery status
- frontmost app
- running applications
- clipboard read and write
- local notifications
- open an application
- resources: `system://status`, `system://applications`
- prompt: `system_capture_context`

## Install On This Mac

<details>
<summary>Quick start</summary>

```bash
cd /path/to/Apple-MCPs/AppleSystem-MCP
./start.sh
```

On first run, `start.sh` creates `.venv`, installs `requirements.txt`, and starts the server over `stdio`.

</details>

## Install In AI Agents

```json
{
  "mcpServers": {
    "apple-system": {
      "command": "/path/to/Apple-MCPs/AppleSystem-MCP/start.sh",
      "args": [],
      "env": {
        "APPLE_SYSTEM_MCP_SAFETY_MODE": "safe_readonly"
      }
    }
  }
}
```

## Prompting Notes

- Use this server when the user’s current desktop context matters.
- Read battery state and the frontmost app before interruptive actions.
- Keep `APPLE_SYSTEM_MCP_SAFETY_MODE=safe_readonly` by default.
- Use `safe_manage` only when the agent truly needs clipboard writes, notifications, or app launches.

## Health And Recovery

- `system_health`
- `system_permission_guide`

## Launch Checklist

- Start the server once with `./start.sh`
- Add `/path/to/Apple-MCPs/AppleSystem-MCP/start.sh` to your MCP client
- Reload or reconnect the client so the System tool surface is loaded into context
- Call `system_health` first
- If a scoped system action is blocked, call `system_permission_guide`
- `system_status`
