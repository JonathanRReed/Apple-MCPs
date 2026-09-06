# Apple-MCPs

![CI](https://github.com/JonathanRReed/Apple-MCPs/actions/workflows/ci.yml/badge.svg)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)
![macOS](https://img.shields.io/badge/macOS-000000?logo=apple&logoColor=white)

MCP servers that let an AI client use Apple apps and macOS tools. Create reminders, send messages, check calendars, search mail, manage files, and get directions.

The servers run on your Mac. Your MCP client may send returned data to its model provider, and Apple apps may sync through iCloud or another account. Local execution does not mean the data stays local.

Requires Python 3.11+ and macOS. Uses MCP specification `2026-07-28` and Python SDK 2.x, with support for older client protocol revisions. [MIT license](LICENSE).

## Install

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then register the unified server with your client.

Claude Code:

```bash
claude mcp add --transport stdio --scope project apple-tools -- uvx apple-tools-mcp
```

Codex:

```bash
codex mcp add apple-tools -- uvx apple-tools-mcp
```

Other stdio clients:

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

Run `uvx apple-tools-mcp` to start the server directly. Standalone servers use the same approach, such as `uvx apple-mcp-mail` or `uvx apple-calendar-mcp`.

Restart your client after installing or upgrading. Call `search_tools` with `calendar health` to check discovery without reading app data.

For Claude Desktop, download a server's `.mcpb` bundle from [Releases](https://github.com/JonathanRReed/Apple-MCPs/releases) and double-click it.

Set app-specific safety modes and directories in your client's `env` settings. The [configuration guide](Apple-Tools-MCP/README.md) lists defaults and options. Mail attachments are disabled until you set `APPLE_MAIL_MCP_ALLOWED_ATTACHMENT_ROOT` to a dedicated directory. Files tools only access `APPLE_FILES_MCP_ALLOWED_ROOTS`; macOS may impose further restrictions.

## Choose a server

Start with [Apple-Tools-MCP](Apple-Tools-MCP/README.md). It combines all ten apps and tools below, plus saved defaults, contact routing, Mail thread helpers, undo, briefings, and cross-app workflows.

Choose a standalone server to expose fewer apps to your client:

| Server | macOS access | Health tool | Permission help |
| --- | --- | --- | --- |
| [Mail](AppleMail-MCP/README.md) | Automation access to Mail | `mail_health` | `mail_permission_guide`, `mail_recheck_permissions` |
| [Calendar](Apple-Calendar-MCP/README.md) | Calendar access | `calendar_health` | `calendar_permission_guide`, `calendar_recheck_permissions` |
| [Reminders](AppleReminders-MCP/README.md) | Reminders access | `reminders_health` | `reminders_permission_guide`, `reminders_recheck_permissions` |
| [Messages](AppleMessages-MCP/README.md) | Automation; Full Disk Access for history | `messages_health` | `messages_permission_guide`, `messages_recheck_permissions` |
| [Contacts](AppleContacts-MCP/README.md) | Contacts access | `contacts_health` | `contacts_permission_guide`, `contacts_recheck_permissions` |
| [Notes](AppleNotes-MCP/README.md) | Automation access to Notes | `notes_health` | `notes_permission_guide`, `notes_recheck_permissions` |
| [Shortcuts](AppleShortcuts-MCP/README.md) | Usually no separate prompt | `shortcuts_health` | `shortcuts_permission_guide`, `shortcuts_refresh_state` |
| [Files](AppleFiles-MCP/README.md) | Allowed roots and protected-folder access | `files_health` | `files_permission_guide` |
| [System](AppleSystem-MCP/README.md) | Some actions need System Events, Accessibility, or Automation | `system_health` | `system_permission_guide` |
| [Maps](AppleMaps-MCP/README.md) | No privacy prompt; Swift helper needs Xcode command line tools | `maps_health` | `maps_permission_guide` |

The unified server uses `apple_health`, `apple_permission_guide`, and `apple_recheck_permissions`. You must approve permissions yourself in the macOS prompt or System Settings.

## Find and use tools

MCP `tools/list` returns each tool's schemas and read or write annotations. Use `search_tools` to search names, descriptions, and aliases; use `get_tool_info` for one tool's schema and examples.

Resolve recipients through Contacts before sending, unless you have the exact address. For Mail conversations, use `mail_get_thread`, `mail_reply_latest_in_thread`, or `mail_archive_thread`. Pass an exact sender email in `from_account` when the sending identity matters.

Mail search requires a query: a sender, subject fragment, or `*`. Reminders `due_date` requires a timezone offset, such as `yyyy-MM-ddTHH:mm:ss-08:00`. Omit `service_name` when sending iMessages.

The unified server also provides `apple_generate_daily_briefing`, `apple_generate_weekly_briefing`, and `apple_triage_communications_task`. Clients without prompt support can use `apple_list_prompts`, `apple_get_prompt`, and their per-server equivalents.

For calls from Python, use the metadata in `generated/tool_catalogs/` and wrappers in `generated/tool_wrappers/python/`. See [code-mode.md](docs/code-mode.md).

## Transport and stored state

`stdio` is the default. To use Streamable HTTP, set `APPLE_<DOMAIN>_MCP_TRANSPORT=streamable-http` and the matching `_HOST` and `_PORT` variables.

HTTP must bind to `127.0.0.1`, `::1`, or `localhost`. The servers have no remote authentication and reject network and wildcard binds. Do not expose them through a tunnel or public proxy.

Apple-Tools-MCP stores defaults in `~/.apple-tools-mcp/preferences.json`, configurable through `APPLE_AGENT_MCP_STATE_FILE`. It stores recent actions in `~/.apple-tools-mcp/actions.json` for audit and undo.

## Develop

```bash
git clone https://github.com/JonathanRReed/Apple-MCPs.git
cd Apple-MCPs
uv sync --all-packages
```

The uv workspace installs every server into `.venv/bin`. Each server folder also has a `start.sh` for clients; it uses uv when available and otherwise creates a virtual environment. Root `pyproject.toml` defines workspace members, and `uv.lock` pins dependencies.

| Path | Contents |
| --- | --- |
| `Apple-Tools-MCP/` | Unified server; module `apple_agent_mcp`, environment prefix `APPLE_AGENT_MCP_*` |
| `Apple<Domain>-MCP/` | Standalone servers; Calendar uses `Apple-Calendar-MCP` |
| `AppleMCPCommon/` | Shared discovery and search, published as `apple-mcp-common` |
| `generated/` | Tool catalogs and Python wrappers |
| `scripts/` | Installation, checks, generation, and bundle builds |
| `docs/` | Project and launch documentation |

Run smoke checks:

```bash
bash scripts/inspector_smoke.sh
uv run python scripts/protocol_smoke.py
```

For the official conformance suite, start the server in a separate terminal:

```bash
APPLE_AGENT_MCP_TRANSPORT=streamable-http \
APPLE_AGENT_MCP_PORT=8765 \
APPLE_AGENT_MCP_CONFORMANCE_MODE=1 \
./Apple-Tools-MCP/start.sh
```

```bash
npx -y @modelcontextprotocol/conformance@0.2.0-alpha.11 server --url http://127.0.0.1:8765/mcp --requirements 2026-07-28
```

Conformance mode registers test fixtures. Use it only for protocol validation. [CI](.github/workflows) runs lint, macOS and Linux tests, generated-file checks, Inspector smoke checks, and conformance tests.

## Documentation

[Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [Troubleshooting](docs/troubleshooting.md) · [MCP compatibility](docs/mcp-compatibility.md) · [Publishing](docs/publishing.md) · [Changelog](CHANGELOG.md) · [Trademark notice](NOTICE.md) · [Launch docs](docs/launch/)
