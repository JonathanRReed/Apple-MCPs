<!-- mcp-name: io.github.JonathanRReed/apple-contacts-mcp -->

# Apple Contacts MCP

MCP server for Apple Contacts on macOS.

Provides access to contacts for lookup, search, and recipient resolution. Use before sending messages to resolve names into phone numbers or email addresses.

## When to use

- Contact-only workflows
- Recipient validation before messaging
- Contact lookup separated from the all-in-one server

## What It Does

- List and search contacts
- Full contact detail lookup
- Message recipient resolution
- Tool discovery helpers `search_tools` and `get_tool_info` for context-constrained clients
- Create, update, and delete contacts
- Duplicate detection and merge-candidate suggestions (`contacts_find_duplicates`, `contacts_suggest_merge_candidates`)
- Phone number and email method editing with labels
- Directory resources and recipient-check prompts
- Health and permission checks: `contacts_health`, `contacts_permission_guide`, `contacts_recheck_permissions`

## Install On This Mac

<details>
<summary>Quick start (uvx, from PyPI)</summary>

With [uv](https://docs.astral.sh/uv/getting-started/installation/) installed:

```bash
uvx apple-contacts-mcp
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

This builds one workspace environment with every server's entry point in `.venv/bin` (for example `.venv/bin/apple-contacts-mcp`). You can also point an MCP client at `AppleContacts-MCP/start.sh`, which prefers `uv run` and falls back to a plain venv bootstrap (Python 3.11+ required).

</details>

## Install In AI Agents

<details>
<summary>Generic MCP client config</summary>

```json
{
  "mcpServers": {
    "apple-contacts": {
      "command": "uvx",
      "args": ["apple-contacts-mcp"],
      "env": {
        "APPLE_CONTACTS_MCP_SAFETY_MODE": "safe_manage"
      }
    }
  }
}
```

Running from a clone instead? Use `/path/to/Apple-MCPs/AppleContacts-MCP/start.sh` as the command with empty `args`.

</details>

<details>
<summary>Claude Code example</summary>

```bash
claude mcp add --transport stdio --scope project apple-contacts -- uvx apple-contacts-mcp
```

</details>

## Safety Modes

- `safe_readonly`
- `safe_manage`
- `full_access`

## Transport

`stdio` is the default and recommended transport. Set `APPLE_CONTACTS_MCP_TRANSPORT=streamable-http` (with optional `APPLE_CONTACTS_MCP_HOST` and `APPLE_CONTACTS_MCP_PORT`) to serve Streamable HTTP instead.

## macOS Permissions

- Contacts access is required
- `contacts_health` reports whether Contacts access is currently available

## Launch Checklist

- Add `uvx apple-contacts-mcp` (or a clone's `AppleContacts-MCP/start.sh`) to your MCP client
- Reload or reconnect the client so the Contacts tool surface is loaded into context
- Call `contacts_health` first
- If Contacts access is blocked, call `contacts_permission_guide`
- After changing macOS permissions, call `contacts_recheck_permissions`

## Prompting Notes

- `tools/list` returns the full Contacts tool surface. Context-constrained clients can use `search_tools` first, then `get_tool_info` for the Contacts tool they need.
- Run Contacts before any iMessage or Mail action when the user gives a person name.
- Resolve by name, phone number, or email before acting.
- If multiple contacts match, confirm the intended person before sending.
- When updating a person, pass explicit `phones` or `emails` arrays only when you intend to replace that method set.
- Keep a labeled phone or email on the contact before routing Messages or Mail through it.

## Related

- [Apple-Tools-MCP](../Apple-Tools-MCP/README.md)
