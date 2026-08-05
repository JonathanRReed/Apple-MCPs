# Contributing

## Scope

This repository contains local MCP servers for Apple apps and adjacent macOS context. Changes should preserve three things:

- macOS-native behavior
- clear permission and safety boundaries
- compatibility with MCP clients that vary in prompt, resource, and task support

## Before You Start

- Read the root [README.md](./README.md) and the README for the server you plan to change.
- Keep changes focused. Do not bundle unrelated refactors.
- Do not commit secrets, tokens, personal data, or machine-specific paths.

## Local Setup

The repository is a [uv](https://docs.astral.sh/uv/) workspace. One command builds an environment with every server installed:

```bash
cd /path/to/Apple-MCPs
uv sync --all-packages
```

Run any server from the workspace venv (`.venv/bin/apple-tools-mcp`, `.venv/bin/apple-mail-mcp`, ...) or via its `start.sh`, which prefers uv and falls back to a plain venv bootstrap.

Most development work uses (config lives in the root `ruff.toml`):

```bash
uv run ruff check .
```

and server-local tests:

```bash
cd /path/to/Apple-MCPs/<server>
uv run --project . python -m pytest
```

The Swift bridge sources are vendored per package (`Apple-Calendar-MCP` and `AppleReminders-MCP` share `apple_pim_bridge.swift`); if you change one copy, run `bash scripts/check_bridge_sync.sh` to confirm the copies still match.

## Required Checks

Run the checks that match your change:

- Docs-only changes: verify links, commands, and server names by reading the affected README files.
- Python changes: run `ruff check .` from the repo root.
- Server behavior changes: run `pytest tests` in each affected server package.
- Unified server changes: run `pytest tests` in `Apple-Tools-MCP`.
- Published-surface changes: run the repo-wide Inspector smoke check:

```bash
cd /path/to/Apple-MCPs
bash scripts/inspector_smoke.sh
```

- Protocol-surface changes in `Apple-Tools-MCP`: run the official active MCP conformance suite over `streamable-http`.

## Contribution Rules

- Match existing naming, safety, and response-shape patterns.
- Add or update tests for behavior changes.
- Keep permission failures explicit and actionable.
- Prefer narrow, auditable tool surfaces over implicit automation.
- Document user-facing changes in the relevant README files.

## Pull Requests

Include:

- what changed
- why it changed
- which packages were affected
- what you ran to verify the change
- any macOS permission or environment assumptions

Use conventional commit prefixes when preparing commits, for example:

- `feat:`
- `fix:`
- `docs:`
- `chore:`

## Good First Contributions

- expand test coverage for existing tools
- improve permission diagnostics
- add better resource or prompt documentation
- tighten manifest metadata and packaging
- improve client compatibility notes
