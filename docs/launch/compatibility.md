# Compatibility and Version Pinning

This repository is optimized for macOS and local MCP execution.

## Tested baseline

- Python: `3.11` – `3.14`
- MCP Python SDK: `2.x` (`mcp>=2.0.0,<3`)
- MCP specification: `2026-07-28`, with SDK-level backward compatibility for clients speaking older protocol revisions
- Pydantic: `>=2.12`

The workspace `uv.lock` at the repo root pins the full dependency graph for development and CI.

## Packaging expectations

- Every server is published to PyPI and runnable with `uvx <package-name>`
- Every standalone server is independently runnable from its own `start.sh` (uv-first, venv fallback)
- `Apple-Tools-MCP` supports dual mode
  - installed standalone packages already available in the environment
  - monorepo fallback through sibling `src/` folders

## Validated protocol surface

Validated in this repo:
- all servers: full `tools/list` with annotations and structured output, plus catalog search through `search_tools` and `get_tool_info`
- selected servers with prompts and resources: Inspector prompt and resource checks
- `Apple-Tools-MCP`: official active MCP conformance suite over `streamable-http`

## Client capability matrix

| Capability | Required for | Notes |
| --- | --- | --- |
| Tools | All servers | Required everywhere |
| Resources | Overview and snapshot reads | Strongly recommended |
| Prompts | Prompt-driven workflows | Optional because prompt fallback tools are exposed |
| Deferred tool loading | Large tool surfaces (Apple-Tools-MCP lists 180+ tools) | Claude clients defer-load automatically; `search_tools` covers others |
| Elicitation | Interactive completion of missing fields | Optional |

## Briefing tools note

The briefing tools (`apple_generate_daily_briefing`, `apple_generate_weekly_briefing`, `apple_triage_communications_task`) are standard synchronous tools as of 1.0.0. The experimental MCP tasks integration they previously used was removed from the MCP specification (SEP-1686); the tool names and results are unchanged.

## Permission-sensitive domains

| Domain | Typical requirement |
| --- | --- |
| Messages | Automation access to Messages, plus Full Disk Access for history |
| Calendar | Calendar access |
| Reminders | Reminders access |
| Contacts | Contacts access |
| Mail | Automation access to Mail |
| Notes | Automation access to Notes |
| Files | Allowed roots configuration |
| System | System Events or app automation prompts for some actions |
| Maps | Xcode command line tools for the local Swift helper |
