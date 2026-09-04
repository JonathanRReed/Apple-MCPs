# Apple-MCPs

![CI](https://github.com/JonathanRReed/Apple-MCPs/actions/workflows/ci.yml/badge.svg)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)
![macOS](https://img.shields.io/badge/macOS-000000?logo=apple&logoColor=white)
![License MIT](https://img.shields.io/badge/license-MIT-green)
![MCP spec 2026-07-28](https://img.shields.io/badge/MCP%20spec-2026--07--28-8A2BE2)

MCP servers for using Apple apps and macOS tools from an AI client.

The servers can create reminders, send messages, check calendars, search mail,
manage files, and get directions through the [Model Context Protocol](https://modelcontextprotocol.io)
(MCP). The integrations run on your Mac and work with the Apple apps you already
use. Data returned to an MCP client may be sent to that client's model provider,
and Apple apps may sync their data through iCloud or another configured account.

Apple-MCPs is free and open source under the [MIT License](./LICENSE).

Built on MCP specification **2026-07-28** (Python SDK 2.x) with backward compatibility for clients speaking older protocol revisions.

## Install

### Run from PyPI (uvx)

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run the unified server:

```bash
uvx apple-tools-mcp
```

Standalone servers work the same way. For example, use `uvx apple-mcp-mail` or
`uvx apple-calendar-mcp`.

### Claude Code

```bash
claude mcp add --transport stdio --scope project apple-tools -- uvx apple-tools-mcp
```

### Codex

Register the unified server with the Codex CLI:

```bash
codex mcp add apple-tools -- uvx apple-tools-mcp
```

Restart the client after installation or upgrades, then call `search_tools`
with a query such as `calendar health` to check discovery without reading app data.

### Generic MCP client (stdio JSON config)

```json
{
  "mcpServers": {
    "apple-tools": {
      "command": "uvx",
      "args": ["apple-tools-mcp"]
    }
  }
}
```

Configure app-specific safety modes and directories in your client's `env`
settings. See the [Apple Tools configuration guide](./Apple-Tools-MCP/README.md)
for the available settings and defaults.

Mail attachments are disabled unless `APPLE_MAIL_MCP_ALLOWED_ATTACHMENT_ROOT`
points to a dedicated directory. Files tools remain limited to
`APPLE_FILES_MCP_ALLOWED_ROOTS`, and macOS privacy controls may further limit
access to folders such as Desktop, Documents, Downloads, or iCloud Drive.

### Claude Desktop

Download the `.mcpb` bundle for a server from [Releases](https://github.com/JonathanRReed/Apple-MCPs/releases)
and double-click it. Claude Desktop installs the bundle and manages its
configuration.

### From a clone

```bash
git clone https://github.com/JonathanRReed/Apple-MCPs.git
cd Apple-MCPs
uv sync --all-packages
```

This creates one workspace environment with every server entry point in
`.venv/bin`, including `.venv/bin/apple-tools-mcp`. Each server folder also has
a `start.sh` that MCP clients can call directly. The script uses uv when it is
available and otherwise creates a plain virtual environment.

## Servers

[Apple-Tools-MCP](./Apple-Tools-MCP/README.md) is the recommended starting point.
It combines Mail, Calendar, Reminders, Messages, Contacts, Notes, Shortcuts,
Files, System, and Maps in one server. It also has saved defaults, per-contact
routing preferences, Mail thread helpers, undo support, briefing tools, and
cross-app workflows.

Use a standalone server when you want to expose fewer Apple apps to the client:

- [Mail](./AppleMail-MCP/README.md)
- [Calendar](./Apple-Calendar-MCP/README.md)
- [Reminders](./AppleReminders-MCP/README.md)
- [Messages](./AppleMessages-MCP/README.md)
- [Contacts](./AppleContacts-MCP/README.md)
- [Notes](./AppleNotes-MCP/README.md)
- [Shortcuts](./AppleShortcuts-MCP/README.md)
- [Files](./AppleFiles-MCP/README.md)
- [System](./AppleSystem-MCP/README.md)
- [Maps](./AppleMaps-MCP/README.md)

## macOS permissions

macOS controls access to Apple apps and protected data. Each server has tools to
report its current access, explain the required permission, and recheck after a
change. You must approve or change macOS permissions yourself in the system
prompt or System Settings.

| Server | What macOS may ask for | Health tool | Recovery tools |
| --- | --- | --- | --- |
| Apple-Tools-MCP | Everything below, as used | `apple_health` | `apple_permission_guide`, `apple_recheck_permissions` |
| Mail | Automation access to Mail | `mail_health` | `mail_permission_guide`, `mail_recheck_permissions` |
| Calendar | Calendar access | `calendar_health` | `calendar_permission_guide`, `calendar_recheck_permissions` |
| Reminders | Reminders access | `reminders_health` | `reminders_permission_guide`, `reminders_recheck_permissions` |
| Messages | Automation access to Messages, plus Full Disk Access for history | `messages_health` | `messages_permission_guide`, `messages_recheck_permissions` |
| Contacts | Contacts access | `contacts_health` | `contacts_permission_guide`, `contacts_recheck_permissions` |
| Notes | Automation access to Notes | `notes_health` | `notes_permission_guide`, `notes_recheck_permissions` |
| Shortcuts | Usually no separate privacy prompt | `shortcuts_health` | `shortcuts_permission_guide`, `shortcuts_refresh_state` |
| Files | Access is limited to configured allowed roots; macOS may also require access to protected folders | `files_health` | `files_permission_guide` |
| System | System Events, Accessibility, or automation prompts for some actions | `system_health` | `system_permission_guide` |
| Maps | No privacy prompt; local Swift helper needs Xcode command line tools | `maps_health` | `maps_permission_guide` |

## Find and use tools

Every server lists its available tools through MCP `tools/list`, including input
and output schemas and read or write annotations. Two helper tools make a large
catalog easier to search:

- `search_tools`: search tool names, descriptions, and aliases
- `get_tool_info`: read the schema, metadata, and examples for one tool

## Usage notes

- Resolve a person through Contacts before sending a message, unless you already have their exact recipient address.
- Use Mail thread helpers (`mail_get_thread`, `mail_reply_latest_in_thread`, `mail_archive_thread`) when the user mentions a conversation.
- Reminders are for due items, Notes for reference material, Calendar for scheduled time.
- When Mail must send from a specific identity, pass the exact sender email in `from_account`.
- Mail search requires a query string: a sender, a subject fragment, or `*` as a wildcard.
- Reminders `due_date` requires a timezone offset like `yyyy-MM-ddTHH:mm:ss-08:00`.
- Omit `service_name` on iMessage sends.
- Apple-Tools-MCP includes briefing tools: `apple_generate_daily_briefing`, `apple_generate_weekly_briefing`, and `apple_triage_communications_task`.
- Prompt-fallback tools (`apple_list_prompts`, `apple_get_prompt`, and per-server equivalents) cover clients that only support tools.

## Python wrappers

The repository includes generated Python wrappers for clients that call MCP tools
from code:

- `generated/tool_catalogs/`: searchable tool metadata for each server
- `generated/tool_wrappers/python/`: Python wrappers for every tool

See [docs/code-mode.md](./docs/code-mode.md) for the wrapper layout, client interface, and recommended workflow.

## Transports and protocol checks

`stdio` is the default transport for local use. Every server also supports
`streamable-http` through environment variables. Set
`APPLE_<DOMAIN>_MCP_TRANSPORT=streamable-http` and the matching `_HOST` and
`_PORT` variables. HTTP binds must use a loopback address such as `127.0.0.1`,
`::1`, or `localhost`. The servers have no remote authentication. They reject
network and wildcard binds and should not be exposed through a tunnel or public
proxy.

Run the official MCP conformance suite against Apple-Tools-MCP:

```bash
APPLE_AGENT_MCP_TRANSPORT=streamable-http \
APPLE_AGENT_MCP_PORT=8765 \
APPLE_AGENT_MCP_CONFORMANCE_MODE=1 \
./Apple-Tools-MCP/start.sh
```

```bash
npx -y @modelcontextprotocol/conformance@0.2.0-alpha.11 server --url http://127.0.0.1:8765/mcp --requirements 2026-07-28
```

Lightweight Inspector smoke checks across all servers:

```bash
bash scripts/inspector_smoke.sh
uv run python scripts/protocol_smoke.py
```

CI runs lint, the full test suite on macOS and Linux, generated-artifact drift
checks, Inspector smoke checks, and the conformance suite. See
[.github/workflows](./.github/workflows).

## Repository layout

- `Apple-Tools-MCP/`: unified server, module `apple_agent_mcp`, environment prefix `APPLE_AGENT_MCP_*`
- `Apple<Domain>-MCP/`: standalone servers. The calendar folder is `Apple-Calendar-MCP`.
- `AppleMCPCommon/`: shared discovery and search helpers, published as `apple-mcp-common`
- `generated/`: generated tool catalogs and Python wrappers
- `scripts/`: install, protocol check, artifact generation, and bundle build scripts
- `docs/`: project and launch documentation

The repository is a uv workspace: `pyproject.toml` at the root defines members, and `uv.lock` pins the whole dependency graph.

## Project documentation

- [CHANGELOG.md](./CHANGELOG.md)
- [CONTRIBUTING.md](./CONTRIBUTING.md)
- [SECURITY.md](./SECURITY.md)
- [Code Mode](./docs/code-mode.md)
- [MCP compatibility](./docs/mcp-compatibility.md)
- [Troubleshooting](./docs/troubleshooting.md): macOS permissions, timeouts, and common error codes
- [Publishing](./docs/publishing.md)
- [NOTICE.md](./NOTICE.md): trademark notice
- [Launch docs](./docs/launch/): workflows, failure modes, compatibility, and demo script

## Notes

- Apple-Tools-MCP persists assistant defaults in `~/.apple-tools-mcp/preferences.json` (or `APPLE_AGENT_MCP_STATE_FILE`) and recent assistant actions in `~/.apple-tools-mcp/actions.json` for audit and undo workflows.
- `APPLE_AGENT_MCP_CONFORMANCE_MODE=1` is for protocol validation only; it registers the official conformance fixtures.
