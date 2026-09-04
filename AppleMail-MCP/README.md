<!-- mcp-name: io.github.JonathanRReed/apple-mcp-mail -->

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
- Tool discovery helpers `search_tools` and `get_tool_info` for context-constrained clients
- Thread helpers: `mail_get_thread`, `mail_reply_latest_in_thread`, `mail_archive_thread`
- Mailbox resources and reply-oriented prompts
- Health and permission checks: `mail_health`, `mail_permission_guide`, `mail_recheck_permissions`

## Tools

`mail_health`, `mail_permission_guide`, `mail_recheck_permissions`, `mail_list_mailboxes`, `mail_search_messages`, `mail_get_message`, `mail_get_thread`, `mail_compose_draft`, `mail_send_message`, `mail_reply_message`, `mail_forward_message`, `mail_mark_message`, `mail_move_message`, `mail_delete_message`, `mail_reply_latest_in_thread`, `mail_archive_thread`, `mail_list_prompts`, `mail_get_prompt`, plus the discovery helpers `search_tools` and `get_tool_info`.

## Install On This Mac

<details>
<summary>Quick start (uvx, from PyPI)</summary>

With [uv](https://docs.astral.sh/uv/getting-started/installation/) installed:

```bash
uvx apple-mcp-mail
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

This builds one workspace environment with every server's entry point in `.venv/bin` (for example `.venv/bin/apple-mail-mcp`). You can also point an MCP client at `AppleMail-MCP/start.sh`, which prefers `uv run` and falls back to a plain venv bootstrap (Python 3.11+ required).

</details>

## Install In AI Agents

<details>
<summary>Generic MCP client config</summary>

```json
{
  "mcpServers": {
    "apple-mail": {
      "command": "uvx",
      "args": ["apple-mcp-mail"],
      "env": {
        "APPLE_MAIL_MCP_SAFETY_PROFILE": "safe_manage",
        "APPLE_MAIL_MCP_VISIBLE_DRAFTS": "true"
      }
    }
  }
}
```

Running from a clone instead? Use `/path/to/Apple-MCPs/AppleMail-MCP/start.sh` as the command with empty `args`.

</details>

<details>
<summary>Claude Code example</summary>

```bash
claude mcp add --transport stdio --scope project apple-mail -- uvx apple-mcp-mail
```

</details>

## Safety Modes

- `safe_readonly`, read and search only
- `safe_manage`, read plus draft creation
- `full_access`, full Mail tool surface in this repo

## Transport

`stdio` is the default and recommended transport. Set `APPLE_MAIL_MCP_TRANSPORT=streamable-http` (with optional `APPLE_MAIL_MCP_HOST` and `APPLE_MAIL_MCP_PORT`) to serve Streamable HTTP instead.

## macOS Permissions

- Automation access to Mail is required

## Launch Checklist

- Add `uvx apple-mcp-mail` (or a clone's `AppleMail-MCP/start.sh`) to your MCP client
- Reload or reconnect the client so the Mail tool surface is loaded into context
- Call `mail_health` first to confirm the server is reachable
- If Mail automation is blocked, call `mail_permission_guide`
- After changing macOS permissions, call `mail_recheck_permissions`

## Prompting Notes

- Run Contacts before any send or reply when the user identifies a person rather than an email address.
- `tools/list` returns the full Mail tool surface. Context-constrained clients can call `search_tools` first, then `get_tool_info` for the exact Mail tool they plan to call.
- `mail_search_messages` requires a query string. Use a sender, a subject fragment, or `*` as a wildcard.
- There is no list-all recent-mail endpoint.
- Use `mail_get_thread` when the user means a conversation, not a single message.
- Use `mail_reply_latest_in_thread` when the agent should reply to the newest message in the conversation.
- Use `mail_archive_thread` when the user wants thread-level cleanup and Archive is the intended mailbox.
- If the user could mean text or email, ask once before choosing Messages or Mail.
- When Mail must send from a specific identity, pass the exact sender email in `from_account`.

## Related

- [Apple-Tools-MCP](../Apple-Tools-MCP/README.md)

## Attachment access

File attachments are disabled until you set `APPLE_MAIL_MCP_ALLOWED_ATTACHMENT_ROOT`
to a directory you choose, such as `~/Documents/Mail Attachments`. This applies to
both drafts and sends, including calls through Apple Tools. The server resolves
symlinks and accepts only regular files inside that directory. Files outside it,
directories, and paths containing the attachment transport separator are rejected.
Mail operations without attachments continue to work with the existing safety profile.
