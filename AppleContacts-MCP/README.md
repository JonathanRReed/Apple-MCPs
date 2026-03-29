# Apple Contacts MCP

Apple Contacts access for AI agents on macOS.

This MCP lets an agent inspect contacts, search by name, phone, or email, fetch full contact details, and resolve a contact into a message-ready recipient before sending through Apple Messages.

## Use This Server When

- you want a contacts-only assistant
- you want to validate or resolve a recipient before messaging
- you want contact lookup separated from the all-in-one server

## What This MCP Gives An Agent

- contact listing
- contact search
- full contact detail lookup
- message-recipient resolution from a contact
- directory resources and recipient-check prompts
- `contacts_health`, `contacts_permission_guide`, and `contacts_recheck_permissions` for launch checks

## Install On This Mac

<details>
<summary>Quick start</summary>

```bash
cd /Users/jonathanreed/Downloads/Apple-MCPs/AppleContacts-MCP
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
      "command": "/Users/jonathanreed/Downloads/Apple-MCPs/AppleContacts-MCP/start.sh",
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
  -- /Users/jonathanreed/Downloads/Apple-MCPs/AppleContacts-MCP/start.sh
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
- Add `/Users/jonathanreed/Downloads/Apple-MCPs/AppleContacts-MCP/start.sh` to your MCP client
- Reload or reconnect the client so the Contacts tool surface is loaded into context
- Call `contacts_health` first
- If Contacts access is blocked, call `contacts_permission_guide`
- After changing macOS permissions, call `contacts_recheck_permissions`

## Prompting Notes

- Run Contacts before any iMessage or Mail action when the user gives a person name.
- Resolve by name, phone number, or email before acting.
- If multiple contacts match, confirm the intended person before sending.

## Related

- [Apple-Tools-MCP](../Apple-Tools-MCP/README.md)
