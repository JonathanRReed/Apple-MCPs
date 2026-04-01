# Apple Contacts MCP

MCP server for Apple Contacts on macOS.

Provides access to contacts for lookup, search, and recipient resolution. Use before sending messages to resolve names into phone numbers or email addresses.

## When to use

- Contact-only assistant workflows
- Recipient validation before messaging
- Contact lookup separated from the all-in-one server

## Capabilities

- Contact listing and search
- Full contact detail lookup
- Message recipient resolution
- Contact creation, update, and delete
- Phone number and email method editing with labels
- Directory resources and recipient-check prompts
- `contacts_health`, `contacts_permission_guide`, and `contacts_recheck_permissions` for launch checks

## Install On This Mac

<details>
<summary>Quick start</summary>

```bash
cd /path/to/Apple-MCPs/AppleContacts-MCP
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
    "apple-contacts": {
      "command": "/path/to/Apple-MCPs/AppleContacts-MCP/start.sh",
      "args": [],
      "env": {
        "APPLE_CONTACTS_MCP_SAFETY_MODE": "safe_readonly"
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
  apple-contacts \
  -- /path/to/Apple-MCPs/AppleContacts-MCP/start.sh
```

</details>

## Safety Modes

- `safe_readonly`
- `safe_manage`
- `full_access`

## macOS Permissions

- Contacts access is required
- `contacts_health` reports whether Contacts access is currently available

## Launch Checklist

- Start the server once with `./start.sh`
- Add `/path/to/Apple-MCPs/AppleContacts-MCP/start.sh` to your MCP client
- Reload or reconnect the client so the Contacts tool surface is loaded into context
- Call `contacts_health` first
- If Contacts access is blocked, call `contacts_permission_guide`
- After changing macOS permissions, call `contacts_recheck_permissions`

## Prompting Notes

- Run Contacts before any iMessage or Mail action when the user gives a person name.
- Resolve by name, phone number, or email before acting.
- If multiple contacts match, confirm the intended person before sending.
- When updating a person, pass explicit `phones` or `emails` arrays only when you intend to replace that method set.
- Keep a labeled phone or email on the contact before routing Messages or Mail through it.

## Related

- [Apple-Tools-MCP](../Apple-Tools-MCP/README.md)
