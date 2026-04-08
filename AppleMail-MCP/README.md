# Apple Mail MCP

MCP server for Apple Mail on macOS.

Provides access to mailboxes, message search, reading, and composition. Keep Mail as the system of record while enabling agents to search, read, draft, and send email.

## When to use

- Mail-only workflows
- Tighter permissions than the all-in-one server
- Draft and send workflows through the native Mail app

## What It Does

- List mailboxes
- Search and read messages
- Create drafts and send messages
- Reply, forward, mark read/unread, move, and delete
- Search-first discovery through `search_tools` and `get_tool_info`
- Thread helpers: `mail_get_thread`, `mail_reply_latest_in_thread`, `mail_archive_thread`
- Mailbox resources and reply-oriented prompts
- Health and permission checks: `mail_health`, `mail_permission_guide`, `mail_recheck_permissions`

## Install On This Mac

<details>
<summary>Quick start</summary>

```bash
cd /path/to/Apple-MCPs/AppleMail-MCP
./start.sh
```

`start.sh` bootstraps and repairs `.venv` as needed, reinstalls when `requirements.txt` changes, and starts the server over `stdio`.

</details>

## Install In AI Agents

<details>
<summary>Generic MCP client config</summary>

```json
{
  "mcpServers": {
    "apple-mail": {
      "command": "/path/to/Apple-MCPs/AppleMail-MCP/start.sh",
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
  -- /path/to/Apple-MCPs/AppleMail-MCP/start.sh
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
- Add `/path/to/Apple-MCPs/AppleMail-MCP/start.sh` to your MCP client
- Reload or reconnect the client so the Mail tool surface is loaded into context
- Call `mail_health` first to confirm the server is reachable
- If Mail automation is blocked, call `mail_permission_guide`
- After changing macOS permissions, call `mail_recheck_permissions`

## Prompting Notes

- Run Contacts before any send or reply when the user identifies a person rather than an email address.
- `tools/list` is intentionally minimal. Use `search_tools` first, then `get_tool_info` for the exact Mail tool you plan to call.
- `mail_search_messages` requires a query string. Use a sender, a subject fragment, or `*` as a wildcard.
- There is no list-all recent-mail endpoint.
- Use `mail_get_thread` when the user means a conversation, not a single message.
- Use `mail_reply_latest_in_thread` when the agent should reply to the newest message in the conversation.
- Use `mail_archive_thread` when the user wants thread-level cleanup and Archive is the intended mailbox.
- If the user could mean text or email, ask once before choosing Messages or Mail.
- When Mail must send from a specific identity, pass the exact sender email in `from_account`, for example `sender@example.com`.

## Related

- [Apple-Tools-MCP](../Apple-Tools-MCP/README.md)
