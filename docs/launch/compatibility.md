# Compatibility and Version Pinning

This repository is optimized for macOS and local MCP execution.

## Tested baseline

- Python: `3.11`
- MCP Python SDK: `1.26.0`
- Pydantic: `2.12.5`

These are the pinned runtime versions used in the repo `requirements.txt` files for the published server folders.

## Packaging expectations

- Every standalone server is independently runnable from its own `start.sh`
- `Apple-Tools-MCP` supports dual mode
  - installed standalone packages already available in the environment
  - monorepo fallback through sibling `src/` folders

## Validated protocol surface

Validated in this repo:
- all servers: `tools/list` via Inspector CLI
- selected servers with prompts and resources: Inspector prompt and resource checks
- `Apple-Tools-MCP`: official active MCP conformance suite over `streamable-http`

## Client capability matrix

| Capability | Required for | Notes |
| --- | --- | --- |
| Tools | All servers | Required everywhere |
| Resources | Overview and snapshot reads | Strongly recommended |
| Prompts | Prompt-driven workflows | Optional because prompt fallback tools are exposed |
| Resource subscriptions | Live resource refresh | Optional, supported where implemented |
| Elicitation | Interactive completion of missing fields | Optional |
| Tasks | `apple_generate_daily_briefing`, `apple_generate_weekly_briefing`, `apple_triage_communications_task` | Optional and experimental |

## Task support note

Task support in `Apple-Tools-MCP` is:
- available
- optional
- experimental

Clients that do not support MCP tasks should still call the same tools directly and accept the returned synchronous result.

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
