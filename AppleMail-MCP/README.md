# Apple Mail MCP

Apple Mail access for AI agents on macOS.

This MCP lets an agent inspect mailboxes, search messages, read message details, compose drafts, and send mail through Apple Mail while keeping Mail as the system of record.

## Use This Server When

- you want an agent to work only with Apple Mail
- you want tighter Mail-only permissions instead of the all-in-one server
- you want draft and send workflows in the native Mail app

## What This MCP Gives An Agent

- mailbox listing
- message search
- message read access
- draft creation
- message sending
- mailbox resources and reply-oriented prompts
- `mail_health`, `mail_permission_guide`, and `mail_recheck_permissions` for launch and permission checks

## Install On This Mac

<details>
<summary>Quick start</summary>

```bash
cd /Users/jonathanreed/Downloads/Apple-MCPs/AppleMail-MCP
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
    "apple-mail": {
      "command": "/Users/jonathanreed/Downloads/Apple-MCPs/AppleMail-MCP/start.sh",
      "args": [],
      "env": {
        "APPLE_MAIL_MCP_SAFETY_PROFILE": "safe_manage",
        "APPLE_MAIL_MCP_VISIBLE_DRAFTS": "true"
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
  apple-mail \
  -- /Users/jonathanreed/Downloads/Apple-MCPs/AppleMail-MCP/start.sh
```

</details>

## Safety Modes

- `safe_readonly`, read and search only
- `safe_manage`, read plus draft creation
- `full_access`, full Mail tool surface in this repo

## macOS Permissions

- Automation access to Mail is required

## Launch Checklist

- Start the server once with `./start.sh`
- Add `/Users/jonathanreed/Downloads/Apple-MCPs/AppleMail-MCP/start.sh` to your MCP client
- Reload or reconnect the client so the Mail tool surface is loaded into context
- Call `mail_health` first to confirm the server is reachable
- If Mail automation is blocked, call `mail_permission_guide`
- After changing macOS permissions, call `mail_recheck_permissions`

## Related

- [Apple-Tools-MCP](../Apple-Tools-MCP/README.md)
