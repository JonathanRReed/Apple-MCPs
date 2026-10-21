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
claude mcp add --transport stdio --scope user apple-mail -- uvx apple-mcp-mail
```

`--scope user` makes the server available in every project. To share it with one repository through its `.mcp.json` instead, use `--scope project`.

</details>

## Safety Modes

Set the mode with `APPLE_MAIL_MCP_SAFETY_PROFILE`:

- `safe_readonly`, read and search only
- `safe_manage`, read, create drafts, reply, forward as a draft, mark, move, delete, and archive threads; new-message sending is blocked. Replies are sent immediately, so this mode can still send mail to people already in a thread. Forwards can go to any address, so they are saved as unsent drafts in Mail for the user to review; switch to `full_access` to send forwards directly
- `full_access`, full Mail tool surface in this repo, including new-message sending

Deleting or archiving does not require switching from `safe_manage` to `full_access`.

Defaults depend on how you installed the server:

| Install | Default | Why |
| --- | --- | --- |
| `uvx`, `pip`, or a clone | `safe_manage` | Code default |
| Claude Desktop bundle (`.mcpb`) | `full_access` | Bundles have always shipped with `full_access`; keeping it means upgrades don't remove sending |

To change it in Claude Desktop, open Settings > Extensions, choose Apple Mail, click Configure, and set "Mail safety mode". In other clients, set `APPLE_MAIL_MCP_SAFETY_PROFILE` in the server's `env` block and restart the client. If a tool is blocked, its error names the setting and the value to use. An invalid or blank value selects `safe_readonly`, and `mail_health` explains it in `safety_mode_warning`.

Attachments are off until you set `APPLE_MAIL_MCP_ALLOWED_ATTACHMENT_ROOT` (bundle setting: "Mail attachment folder") to a dedicated folder.

## Transport

`stdio` is the default and recommended transport. Set `APPLE_MAIL_MCP_TRANSPORT=streamable-http` (with optional `APPLE_MAIL_MCP_HOST` and `APPLE_MAIL_MCP_PORT`) to serve Streamable HTTP instead.

## macOS Permissions

- Automation access to Mail is required

## Troubleshooting move/delete errors

[Issue #23](https://github.com/JonathanRReed/Apple-MCPs/issues/23) reports AppleScript `-1728` errors containing `item ... of every message/mailbox/account`. The move and delete scripts now resolve account/mailbox matches into concrete objects and look up messages by Mail's numeric ID within the original mailbox, instead of retaining positional repeat-loop references. They refuse missing or ambiguous targets and do not automatically retry mutations.

Use `message_id` exactly as returned by `mail_search_messages`. If the message has moved or the ID no longer resolves in its original mailbox, search again rather than editing the ID. `ACCOUNT_AMBIGUOUS`, `MAILBOX_AMBIGUOUS`, and their `TARGET_` counterparts mean the configured names do not uniquely identify the requested object; make the selection unambiguous before retrying. Other native errors, including permission errors, remain visible.

For archiving, call `mail_list_mailboxes` and pass the actual destination name. Do not assume the account exposes a mailbox literally named `Archive`, particularly with localized or nested Gmail labels. Keep the intended account explicit when moving between accounts.

A successful `mail_health` response does not verify a move/delete round trip. Validate a new installation using disposable messages with unique subjects: search, perform one requested operation, and confirm the outcome in Mail. Thread archiving moves messages individually and is not transactional; after an error, inspect Mail before retrying the whole thread.

Restart the MCP client after upgrading. A fix merged on GitHub is not available to `uvx` installations from PyPI until a package release includes it. A source checkout can be tested through the clone instructions above; use `Apple-Tools-MCP/start.sh` for the unified server. If an error persists, report the installed version or source commit, macOS version, operation, and redacted error text. Do not post message bodies or private account details.

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
- Pass `account` (an account name from `mail_list_mailboxes`) to search one account. Without it, accounts are searched in Mail's order and stop once `limit` results are collected, so a busy first account can fill the whole result set and hide mailboxes with the same name in other accounts.
- There is no list-all recent-mail endpoint.
- Use `mail_get_thread` when the user means a conversation, not a single message.
- Use `mail_reply_latest_in_thread` when the agent should reply to the newest message in the conversation.
- Use `mail_archive_thread` when the user wants thread-level cleanup and Archive is the intended mailbox.
- If the user could mean text or email, ask once before choosing Messages or Mail.
- When Mail must send from a specific identity, pass the exact sender email in `from_account`.
- `from_account` is applied through Mail's own `sender` property (`Full Name <address>`, with the name quoted when it contains a comma or quote), which needs no extra macOS permissions. Only if Mail does not accept it does the server fall back to picking the From pop-up via System Events, which additionally needs Automation consent for System Events and Accessibility for the process running the server.
- Every AppleScript call is bounded by `APPLE_MAIL_MCP_SCRIPT_TIMEOUT_SECONDS` (whole seconds, default `120`, minimum `5`; an invalid or smaller value uses the default) so a pending macOS consent prompt surfaces as an error instead of a hung request. The default leaves room for slow but legitimate searches: a subject/sender search of a 4,900-message Exchange mailbox took about 56 seconds.
- If `mail_send_message`, `mail_reply_message`, `mail_reply_latest_in_thread` or a sending `mail_forward_message` times out, the result is `SEND_STATUS_UNKNOWN`, not a failure: Mail may already have sent it. Check the account's Sent mailbox (`mail_search_messages` with `mailbox` set to `Sent Messages`, or the name `mail_list_mailboxes` shows, such as `Sent Items`) before retrying, or the message can go out twice.

## Related

- [Apple-Tools-MCP](../Apple-Tools-MCP/README.md)

## Attachment access

File attachments are disabled until you set `APPLE_MAIL_MCP_ALLOWED_ATTACHMENT_ROOT`
to a directory you choose, such as `~/Documents/Mail Attachments`. This applies to
both drafts and sends, including calls through Apple Tools. The server resolves
symlinks and accepts only regular files inside that directory. Files outside it,
directories, and paths containing the attachment transport separator are rejected.
Mail operations without attachments continue to work with the existing safety profile.
