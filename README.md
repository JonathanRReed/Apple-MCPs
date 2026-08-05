# Apple-MCPs

![CI](https://github.com/JonathanRReed/Apple-MCPs/actions/workflows/ci.yml/badge.svg)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)
![macOS](https://img.shields.io/badge/macOS-000000?logo=apple&logoColor=white)
![License MIT](https://img.shields.io/badge/license-MIT-green)
![MCP spec 2026-07-28](https://img.shields.io/badge/MCP%20spec-2026--07--28-8A2BE2)

Apple-native MCP servers for macOS — turn any AI agent into what Siri should have been.

This repository provides direct, local access to core Apple apps through the [Model Context Protocol](https://modelcontextprotocol.io) (MCP). Your AI assistant can use structured tools to work with your data — create reminders, send messages, check calendars, search mail, manage files, get directions — while everything stays in the native apps you already use.

Everything happens on your Mac over local `stdio`. Your data stays in Apple's apps where it belongs. Free and open source under the [MIT License](./LICENSE).

Built on MCP specification **2026-07-28** (Python SDK 2.x) with backward compatibility for clients speaking older protocol revisions.

## Servers

- [Apple-Tools-MCP](./Apple-Tools-MCP/README.md), recommended. One unified server for Mail, Calendar, Reminders, Messages, Contacts, Notes, Shortcuts, Files, System, and Maps — plus saved defaults, per-contact routing preferences, thread-aware Mail helpers, undo support, briefing tools, and cross-app workflows.
- Standalone servers when you want tighter boundaries or simpler permissions:
  [Mail](./AppleMail-MCP/README.md) ·
  [Calendar](./Apple-Calendar-MCP/README.md) ·
  [Reminders](./AppleReminders-MCP/README.md) ·
  [Messages](./AppleMessages-MCP/README.md) ·
  [Contacts](./AppleContacts-MCP/README.md) ·
  [Notes](./AppleNotes-MCP/README.md) ·
  [Shortcuts](./AppleShortcuts-MCP/README.md) ·
  [Files](./AppleFiles-MCP/README.md) ·
  [System](./AppleSystem-MCP/README.md) ·
  [Maps](./AppleMaps-MCP/README.md)

## Install

### Run from PyPI (uvx)

Once you have [uv](https://docs.astral.sh/uv/getting-started/installation/) installed, every server runs with a one-liner — no clone, no venv management:

```bash
uvx apple-tools-mcp
```

Standalone servers work the same way (`uvx apple-mail-mcp`, `uvx apple-calendar-mcp`, ...).

### Claude Code

```bash
claude mcp add --transport stdio --scope project apple-tools -- uvx apple-tools-mcp
```

### Generic MCP client (stdio JSON config)

```json
{
  "mcpServers": {
    "apple-tools": {
      "command": "uvx",
      "args": ["apple-tools-mcp"],
      "env": {
        "APPLE_MAIL_MCP_SAFETY_PROFILE": "full_access",
        "APPLE_CALENDAR_MCP_SAFETY_MODE": "safe_manage",
        "APPLE_REMINDERS_MCP_SAFETY_MODE": "safe_manage",
        "APPLE_FILES_MCP_ALLOWED_ROOTS": "/Users/you/Desktop,/Users/you/Documents,/Users/you/Downloads,/Users/you/Library/Mobile Documents/com~apple~CloudDocs",
        "APPLE_FILES_MCP_SAFETY_MODE": "safe_manage",
        "APPLE_SYSTEM_MCP_SAFETY_MODE": "safe_manage",
        "APPLE_CONTACTS_MCP_SAFETY_MODE": "safe_manage",
        "APPLE_NOTES_MCP_SAFETY_MODE": "full_access",
        "APPLE_MESSAGES_MCP_SAFETY_MODE": "full_access",
        "APPLE_SHORTCUTS_MCP_SAFETY_MODE": "full_access"
      }
    }
  }
}
```

See [Apple-Tools-MCP/README.md](./Apple-Tools-MCP/README.md) for the assistant-grade safety settings recommended for daily use.

### Claude Desktop (one-click bundle)

Download the `.mcpb` bundle for a server from [Releases](https://github.com/JonathanRReed/Apple-MCPs/releases) and double-click it — Claude Desktop installs and manages it, including configuration.

### From a clone

```bash
git clone https://github.com/JonathanRReed/Apple-MCPs.git
cd Apple-MCPs
uv sync --all-packages
```

That builds one workspace environment with every server's entry point in `.venv/bin` (for example `.venv/bin/apple-tools-mcp`). Each server folder also has a `start.sh` that MCP clients can point at directly — it prefers uv and falls back to a plain venv bootstrap.

## macOS Permissions

Different Apple apps require different permissions. Each server ships a health tool, a permission guide tool, and a recheck tool, so your agent can diagnose and fix permission problems by itself.

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
| Files | No privacy prompt; access limited to configured allowed roots | `files_health` | `files_permission_guide` |
| System | System Events, Accessibility, or automation prompts for some actions | `system_health` | `system_permission_guide` |
| Maps | No privacy prompt; local Swift helper needs Xcode command line tools | `maps_health` | `maps_permission_guide` |

## Tool Discovery

Servers expose their full tool surface through `tools/list` (with `readOnlyHint`/`destructiveHint` annotations and structured output schemas), which is what modern deferred-loading clients expect. For context-constrained clients, every server also ships two helper tools:

- `search_tools` — ranked keyword/alias search over the server's tool catalog
- `get_tool_info` — full schema, metadata, and example calls for one tool

## Agent Routing

Some tips for working with these servers:

- Always run Contacts first when messaging a person, then choose Messages or Mail.
- Use Mail thread helpers (`mail_get_thread`, `mail_reply_latest_in_thread`, `mail_archive_thread`) when the user mentions a conversation.
- Reminders are for due items, Notes for reference material, Calendar for scheduled time.
- When Mail must send from a specific identity, pass the exact sender email in `from_account`.
- Mail search requires a query string: a sender, a subject fragment, or `*` as a wildcard.
- Reminders `due_date` requires a timezone offset like `yyyy-MM-ddTHH:mm:ss-08:00`.
- Omit `service_name` on iMessage sends.
- Apple-Tools-MCP includes briefing tools: `apple_generate_daily_briefing`, `apple_generate_weekly_briefing`, and `apple_triage_communications_task`.
- Prompt-fallback tools (`apple_list_prompts`, `apple_get_prompt`, and per-server equivalents) cover clients that only support tools.

## Code-Mode Wrappers

For code-execution clients, the repo ships generated artifacts so agents can call tools as Python functions without loading every schema into context:

- `generated/tool_catalogs/` — searchable tool metadata per server
- `generated/tool_wrappers/python/` — generated Python wrappers for every tool

See [docs/code-mode.md](./docs/code-mode.md) for the wrapper layout, client interface, and recommended workflow.

## Transports and Protocol Verification

`stdio` is the default and recommended transport for local use. Every server also supports `streamable-http` via env vars (`APPLE_<DOMAIN>_MCP_TRANSPORT=streamable-http`, plus `_HOST`/`_PORT`).

Run the official MCP conformance suite against Apple-Tools-MCP:

```bash
APPLE_AGENT_MCP_TRANSPORT=streamable-http \
APPLE_AGENT_MCP_PORT=8765 \
APPLE_AGENT_MCP_CONFORMANCE_MODE=1 \
./Apple-Tools-MCP/start.sh
```

```bash
npx -y @modelcontextprotocol/conformance server --url http://127.0.0.1:8765/mcp --suite active
```

Lightweight Inspector smoke checks across all servers:

```bash
bash scripts/inspector_smoke.sh
```

CI runs lint, the full test suite (macOS and Linux), generated-artifact drift checks, Inspector smoke checks, and the conformance suite — see [.github/workflows](./.github/workflows).

## Repo Layout

- `Apple-Tools-MCP/` — unified server (module `apple_agent_mcp`, env prefix `APPLE_AGENT_MCP_*`)
- `Apple<Domain>-MCP/` — standalone servers (`Apple-Calendar-MCP` is the calendar server)
- `AppleMCPCommon/` — shared discovery/search helpers (`apple-mcp-common` on PyPI)
- `generated/` — code-mode catalogs and wrappers (regenerated by CI checks)
- `scripts/` — install, smoke-check, artifact-generation, and bundle-build helpers
- `docs/` — project and launch docs

The repository is a uv workspace: `pyproject.toml` at the root defines members, and `uv.lock` pins the whole dependency graph.

## Project Docs

- [CHANGELOG.md](./CHANGELOG.md)
- [CONTRIBUTING.md](./CONTRIBUTING.md)
- [SECURITY.md](./SECURITY.md)
- [Code Mode](./docs/code-mode.md)
- [Publishing](./docs/publishing.md)
- [NOTICE.md](./NOTICE.md) — trademark notice
- [Launch docs](./docs/launch/) — golden workflows, failure modes, compatibility, demo script

## Notes

- This suite is for macOS. Apple Messages history access needs Full Disk Access.
- Apple Files access is limited to the roots in `APPLE_FILES_MCP_ALLOWED_ROOTS`.
- Apple System write actions can be scoped down with `APPLE_SYSTEM_MCP_SAFETY_MODE`.
- Apple Maps depends on a local Swift helper compiled with Xcode command line tools.
- Apple-Tools-MCP persists assistant defaults in `~/.apple-tools-mcp/preferences.json` (or `APPLE_AGENT_MCP_STATE_FILE`) and recent assistant actions in `~/.apple-tools-mcp/actions.json` for audit and undo workflows.
- `APPLE_AGENT_MCP_CONFORMANCE_MODE=1` is for protocol validation only; it registers the official conformance fixtures.
