# Apple Mail MCP

MCP server for Apple Mail on macOS.

Provides access to mailboxes, message search, reading, and composition. Keep Mail as the system of record while enabling agents to search, read, draft, and send email.

## When to use

- Mail-only assistant workflows
- Tighter Mail-only permissions instead of the all-in-one server
- Draft and send workflows through the native Mail app

## Capabilities

- Mailbox listing
- Message search and read access
- Draft creation and message sending
- Mailbox resources and reply-oriented prompts
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

## Prompting Notes

- Run Contacts before any send or reply when the user identifies a person rather than an email address.
- `mail_search_messages` requires a query string. Use a sender, a subject fragment, or `*` as a wildcard.
- There is no list-all recent-mail endpoint.
- If the user could mean text or email, ask once before choosing Messages or Mail.

## Related

- [Apple-Tools-MCP](../Apple-Tools-MCP/README.md)
